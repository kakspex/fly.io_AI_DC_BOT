import os
import asyncio
import uuid
import aiohttp
import discord
from discord import app_commands

HF_API = "https://kakspex-DC_AI.hf.space"
TOKEN = os.environ.get("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

pending_tasks = {}
task_lock = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

http_session = None

async def queue_task(prompt):
    prompt = prompt.strip()
    if len(prompt) > 500:
        prompt = prompt[:500]
    async with task_lock:
        try:
            async with asyncio.timeout(15):
                async with http_session.post(f"{HF_API}/generate", json={"prompt": prompt}) as r:
                    data = await r.json()
                    return data.get("task_id", None)
        except:
            return None

async def wait_for_result(task_id):
    if not task_id:
        return "invalid"
    try:
        while True:
            await asyncio.sleep(1)
            async with asyncio.timeout(20):
                async with http_session.get(f"{HF_API}/result/{task_id}") as r2:
                    if r2.status == 404:
                        return "task not found"
                    j = await r2.json()
                    status = j.get("status", "")
                    if status == "completed":
                        return j.get("output", "")
                    if status in ("error", "failed"):
                        return j.get("output", "") or status
    except:
        return "error"

@tree.command(name="ai")
async def ai_command(interaction, prompt: str):
    await interaction.response.defer()
    try:
        task_id = await queue_task(prompt)
        if not task_id:
            await interaction.edit_original_response(content="request error")
            return
        result = await wait_for_result(task_id)
        await interaction.edit_original_response(content=result)
    except:
        await interaction.edit_original_response(content="error")

@tree.command(name="queue")
async def queue_command(interaction, prompt: str):
    async with task_lock:
        task_id = str(uuid.uuid4())
        pending_tasks[task_id] = prompt.strip()[:500]
    await interaction.response.send_message("Task added: " + task_id)

@tree.command(name="runqueue")
async def runqueue(interaction):
    await interaction.response.send_message("Running queue")
    async with task_lock:
        keys = list(pending_tasks.keys())
    for task_id in keys:
        async with task_lock:
            prompt = pending_tasks.get(task_id)
        try:
            real_task = await queue_task(prompt)
            result = await wait_for_result(real_task)
            await interaction.followup.send("Task " + task_id + ": " + result)
        except:
            await interaction.followup.send("Task " + task_id + ": error")
        async with task_lock:
            if task_id in pending_tasks:
                del pending_tasks[task_id]

@tree.command(name="ping")
async def ping(interaction):
    await interaction.response.send_message("Pong")

@client.event
async def on_ready():
    await tree.sync()

async def start():
    global http_session
    http_session = aiohttp.ClientSession()
    try:
        await client.start(TOKEN)
    finally:
        await http_session.close()

asyncio.run(start())
