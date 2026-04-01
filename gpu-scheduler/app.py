"""GPU Task Scheduler - Python Backend"""
import asyncio
import json
import time
import uuid
import random
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional
from aiohttp import web
import aiohttp_cors

# === Enums ===
class GPUStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    FAULT = "fault"

class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# === Data Models ===
@dataclass
class GPU:
    id: str
    name: str
    status: GPUStatus = GPUStatus.IDLE
    current_task: Optional[str] = None
    added_at: float = field(default_factory=time.time)

@dataclass
class Task:
    id: str
    user_id: str
    name: str
    duration: int  # seconds to simulate
    status: TaskStatus = TaskStatus.QUEUED
    gpu_id: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress: float = 0.0

@dataclass
class User:
    id: str
    name: str
    joined_at: float = field(default_factory=time.time)
    active: bool = True

# === Scheduler Core ===
class GPUScheduler:
    def __init__(self):
        self.gpus: dict[str, GPU] = {}
        self.tasks: dict[str, Task] = {}
        self.users: dict[str, User] = {}
        self.queue: list[str] = []  # task ids in FIFO order
        self.lock = asyncio.Lock()
        self.ws_clients: list[web.WebSocketResponse] = []
        self._running_tasks: dict[str, asyncio.Task] = {}
        self.event_log: list[dict] = []

    def _log(self, msg: str):
        entry = {"time": time.time(), "msg": msg}
        self.event_log.append(entry)
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]

    async def broadcast(self, event_type: str, data: dict = None):
        msg = json.dumps({"type": event_type, "data": data or {}, "ts": time.time()})
        dead = []
        for ws in self.ws_clients:
            try:
                await ws.send_str(msg)
            except:
                dead.append(ws)
        for ws in dead:
            self.ws_clients.remove(ws)

    async def add_gpu(self, name: str) -> GPU:
        async with self.lock:
            gpu = GPU(id=str(uuid.uuid4())[:8], name=name)
            self.gpus[gpu.id] = gpu
            self._log(f"GPU [{gpu.name}] added")
        await self.broadcast("update")
        await self._try_schedule()
        return gpu

    async def remove_gpu(self, gpu_id: str) -> bool:
        async with self.lock:
            gpu = self.gpus.get(gpu_id)
            if not gpu:
                return False
            # Cancel running task on this GPU
            if gpu.current_task and gpu.current_task in self._running_tasks:
                self._running_tasks[gpu.current_task].cancel()
                task = self.tasks.get(gpu.current_task)
                if task:
                    task.status = TaskStatus.QUEUED
                    task.gpu_id = None
                    task.started_at = None
                    task.progress = 0.0
                    self.queue.insert(0, task.id)  # re-queue at front
            del self.gpus[gpu_id]
            self._log(f"GPU [{gpu.name}] removed")
        await self.broadcast("update")
        await self._try_schedule()
        return True

    async def fault_gpu(self, gpu_id: str) -> bool:
        async with self.lock:
            gpu = self.gpus.get(gpu_id)
            if not gpu:
                return False
            gpu.status = GPUStatus.FAULT
            if gpu.current_task and gpu.current_task in self._running_tasks:
                self._running_tasks[gpu.current_task].cancel()
                task = self.tasks.get(gpu.current_task)
                if task:
                    task.status = TaskStatus.FAILED
                    task.finished_at = time.time()
                    task.gpu_id = None
            gpu.current_task = None
            self._log(f"GPU [{gpu.name}] faulted")
        await self.broadcast("update")
        return True

    async def repair_gpu(self, gpu_id: str) -> bool:
        async with self.lock:
            gpu = self.gpus.get(gpu_id)
            if not gpu or gpu.status != GPUStatus.FAULT:
                return False
            gpu.status = GPUStatus.IDLE
            self._log(f"GPU [{gpu.name}] repaired")
        await self.broadcast("update")
        await self._try_schedule()
        return True

    async def add_user(self, name: str) -> User:
        async with self.lock:
            user = User(id=str(uuid.uuid4())[:8], name=name)
            self.users[user.id] = user
            self._log(f"User [{user.name}] joined")
        await self.broadcast("update")
        return user

    async def remove_user(self, user_id: str) -> bool:
        async with self.lock:
            user = self.users.get(user_id)
            if not user:
                return False
            user.active = False
            # Cancel all queued tasks
            to_remove = []
            for tid in self.queue:
                t = self.tasks[tid]
                if t.user_id == user_id:
                    t.status = TaskStatus.CANCELLED
                    t.finished_at = time.time()
                    to_remove.append(tid)
            for tid in to_remove:
                self.queue.remove(tid)
            # Cancel running tasks
            for t in self.tasks.values():
                if t.user_id == user_id and t.status == TaskStatus.RUNNING:
                    if t.id in self._running_tasks:
                        self._running_tasks[t.id].cancel()
                    t.status = TaskStatus.CANCELLED
                    t.finished_at = time.time()
                    if t.gpu_id and t.gpu_id in self.gpus:
                        self.gpus[t.gpu_id].status = GPUStatus.IDLE
                        self.gpus[t.gpu_id].current_task = None
                    t.gpu_id = None
            self._log(f"User [{user.name}] left, tasks cancelled")
        await self.broadcast("update")
        await self._try_schedule()
        return True

    async def submit_task(self, user_id: str, name: str, duration: int) -> Optional[Task]:
        async with self.lock:
            user = self.users.get(user_id)
            if not user or not user.active:
                return None
            task = Task(id=str(uuid.uuid4())[:8], user_id=user_id, name=name, duration=duration)
            self.tasks[task.id] = task
            self.queue.append(task.id)
            self._log(f"Task [{task.name}] submitted by [{user.name}]")
        await self.broadcast("update")
        await self._try_schedule()
        return task

    async def cancel_task(self, task_id: str) -> bool:
        async with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            if task.status == TaskStatus.QUEUED:
                task.status = TaskStatus.CANCELLED
                task.finished_at = time.time()
                if task_id in self.queue:
                    self.queue.remove(task_id)
            elif task.status == TaskStatus.RUNNING:
                if task_id in self._running_tasks:
                    self._running_tasks[task_id].cancel()
                task.status = TaskStatus.CANCELLED
                task.finished_at = time.time()
                if task.gpu_id and task.gpu_id in self.gpus:
                    self.gpus[task.gpu_id].status = GPUStatus.IDLE
                    self.gpus[task.gpu_id].current_task = None
                task.gpu_id = None
            else:
                return False
            self._log(f"Task [{task.name}] cancelled")
        await self.broadcast("update")
        await self._try_schedule()
        return True

    async def _try_schedule(self):
        async with self.lock:
            idle_gpus = [g for g in self.gpus.values() if g.status == GPUStatus.IDLE]
            while self.queue and idle_gpus:
                task_id = self.queue.pop(0)
                task = self.tasks.get(task_id)
                if not task or task.status != TaskStatus.QUEUED:
                    continue
                gpu = idle_gpus.pop(0)
                task.status = TaskStatus.RUNNING
                task.gpu_id = gpu.id
                task.started_at = time.time()
                gpu.status = GPUStatus.BUSY
                gpu.current_task = task.id
                self._log(f"Task [{task.name}] → GPU [{gpu.name}]")
                # Start simulated execution
                self._running_tasks[task.id] = asyncio.create_task(
                    self._run_task(task.id)
                )
        await self.broadcast("update")

    async def _run_task(self, task_id: str):
        task = self.tasks[task_id]
        try:
            steps = max(task.duration, 1)
            for i in range(steps):
                await asyncio.sleep(1)
                async with self.lock:
                    if task.status != TaskStatus.RUNNING:
                        return
                    task.progress = (i + 1) / steps * 100
                if (i + 1) % 2 == 0 or i == steps - 1:
                    await self.broadcast("progress", {"task_id": task_id, "progress": task.progress})

            # Random failure 5% chance
            failed = random.random() < 0.05
            async with self.lock:
                if task.status != TaskStatus.RUNNING:
                    return
                task.status = TaskStatus.FAILED if failed else TaskStatus.COMPLETED
                task.finished_at = time.time()
                task.progress = 100
                if task.gpu_id and task.gpu_id in self.gpus:
                    self.gpus[task.gpu_id].status = GPUStatus.IDLE
                    self.gpus[task.gpu_id].current_task = None
                self._log(f"Task [{task.name}] {'FAILED' if failed else 'completed'}")
            await self.broadcast("update")
            await self._try_schedule()
        except asyncio.CancelledError:
            pass
        finally:
            self._running_tasks.pop(task_id, None)

    def get_state(self) -> dict:
        return {
            "gpus": [asdict(g) for g in self.gpus.values()],
            "tasks": [asdict(t) for t in self.tasks.values()],
            "users": [asdict(u) for u in self.users.values()],
            "queue": self.queue,
            "log": self.event_log[-50:],
            "stats": {
                "total_gpus": len(self.gpus),
                "idle_gpus": sum(1 for g in self.gpus.values() if g.status == GPUStatus.IDLE),
                "busy_gpus": sum(1 for g in self.gpus.values() if g.status == GPUStatus.BUSY),
                "fault_gpus": sum(1 for g in self.gpus.values() if g.status == GPUStatus.FAULT),
                "queued_tasks": len(self.queue),
                "running_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING),
                "completed_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
                "active_users": sum(1 for u in self.users.values() if u.active),
            }
        }


# === Web Handlers ===
scheduler = GPUScheduler()

async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    scheduler.ws_clients.append(ws)
    await ws.send_str(json.dumps({"type": "state", "data": scheduler.get_state()}))
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            pass  # client doesn't send commands via WS
    scheduler.ws_clients.remove(ws) if ws in scheduler.ws_clients else None
    return ws

async def handle_state(request):
    return web.json_response(scheduler.get_state())

async def handle_add_gpu(request):
    data = await request.json()
    gpu = await scheduler.add_gpu(data.get("name", f"GPU-{len(scheduler.gpus)}"))
    return web.json_response(asdict(gpu))

async def handle_remove_gpu(request):
    gpu_id = request.match_info["id"]
    ok = await scheduler.remove_gpu(gpu_id)
    return web.json_response({"ok": ok})

async def handle_fault_gpu(request):
    gpu_id = request.match_info["id"]
    ok = await scheduler.fault_gpu(gpu_id)
    return web.json_response({"ok": ok})

async def handle_repair_gpu(request):
    gpu_id = request.match_info["id"]
    ok = await scheduler.repair_gpu(gpu_id)
    return web.json_response({"ok": ok})

async def handle_add_user(request):
    data = await request.json()
    user = await scheduler.add_user(data.get("name", f"User-{len(scheduler.users)}"))
    return web.json_response(asdict(user))

async def handle_remove_user(request):
    user_id = request.match_info["id"]
    ok = await scheduler.remove_user(user_id)
    return web.json_response({"ok": ok})

async def handle_submit_task(request):
    data = await request.json()
    task = await scheduler.submit_task(
        data["user_id"], data.get("name", "Unnamed"), data.get("duration", 10)
    )
    if task:
        return web.json_response(asdict(task))
    return web.json_response({"error": "Invalid user"}, status=400)

async def handle_cancel_task(request):
    task_id = request.match_info["id"]
    ok = await scheduler.cancel_task(task_id)
    return web.json_response({"ok": ok})

import aiohttp

app = web.Application()
app.router.add_get("/ws", handle_ws)
app.router.add_get("/api/state", handle_state)
app.router.add_post("/api/gpu", handle_add_gpu)
app.router.add_delete("/api/gpu/{id}", handle_remove_gpu)
app.router.add_post("/api/gpu/{id}/fault", handle_fault_gpu)
app.router.add_post("/api/gpu/{id}/repair", handle_repair_gpu)
app.router.add_post("/api/user", handle_add_user)
app.router.add_delete("/api/user/{id}", handle_remove_user)
app.router.add_post("/api/task", handle_submit_task)
app.router.add_delete("/api/task/{id}", handle_cancel_task)

# CORS
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
        allow_methods="*",
    )
})
for route in list(app.router.routes()):
    try:
        cors.add(route)
    except:
        pass

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=7690)
