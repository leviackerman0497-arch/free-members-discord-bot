import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("free-members-discord-bot")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


BOT_TOKEN = required_env("DISCORD_BOT_TOKEN")
MAIN_SERVER_ID = int(os.getenv("MAIN_SERVER_ID", "0"))
LEAVE_AFTER_DAYS = int(os.getenv("LEAVE_AFTER_DAYS", "14"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=("!", "?"), intents=intents, help_command=None)
server_join_times: dict[int, datetime] = {}


async def send_main_server_notice(embed: discord.Embed) -> None:
    if not MAIN_SERVER_ID:
        return
    guild = bot.get_guild(MAIN_SERVER_ID)
    if not guild:
        return
    for channel in guild.text_channels:
        permissions = channel.permissions_for(guild.me) if guild.me else None
        if permissions and permissions.send_messages:
            await channel.send(embed=embed)
            return


@bot.event
async def on_ready() -> None:
    logger.info("Bot is ready as %s", bot.user)
    for guild in bot.guilds:
        if guild.id != MAIN_SERVER_ID:
            server_join_times.setdefault(guild.id, datetime.now(timezone.utc))
    if not check_server_ages.is_running():
        check_server_ages.start()
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d application commands", len(synced))
    except discord.HTTPException:
        logger.exception("Could not sync application commands")


@tasks.loop(hours=24)
async def check_server_ages() -> None:
    now = datetime.now(timezone.utc)
    for guild in list(bot.guilds):
        if guild.id == MAIN_SERVER_ID:
            continue
        joined_at = server_join_times.setdefault(guild.id, now)
        age = now - joined_at
        if age >= timedelta(days=LEAVE_AFTER_DAYS):
            logger.info("Leaving %s (%s) after %d days", guild.name, guild.id, age.days)
            embed = discord.Embed(
                title="Bot left a server",
                description=(
                    f"**Server:** {guild.name}\n**ID:** `{guild.id}`\n"
                    f"**Reason:** membership exceeded {LEAVE_AFTER_DAYS} days"
                ),
                color=discord.Color.red(),
                timestamp=now,
            )
            try:
                await guild.leave()
                await send_main_server_notice(embed)
            except discord.HTTPException:
                logger.exception("Could not leave %s", guild.id)
            finally:
                server_join_times.pop(guild.id, None)


@check_server_ages.before_loop
async def before_check_server_ages() -> None:
    await bot.wait_until_ready()


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    if guild.id == MAIN_SERVER_ID:
        return
    server_join_times[guild.id] = datetime.now(timezone.utc)
    logger.info("Joined %s (%s)", guild.name, guild.id)
    await send_main_server_notice(
        discord.Embed(
            title="Bot joined a server",
            description=(
                f"**Server:** {guild.name}\n**ID:** `{guild.id}`\n"
                f"**Members:** {guild.member_count or 'unknown'}\n"
                f"**Automatic departure:** {LEAVE_AFTER_DAYS} days"
            ),
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
    )


@bot.event
async def on_guild_remove(guild: discord.Guild) -> None:
    server_join_times.pop(guild.id, None)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Unknown command. Use `!help` to see the available commands.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument. Use `!help` for command examples.")
    else:
        logger.exception("Command error", exc_info=error)
        await ctx.send("Something went wrong while running that command.")


@bot.hybrid_command(name="servers", description="List the servers where the bot is installed")
async def list_servers(ctx: commands.Context) -> None:
    if not bot.guilds:
        await ctx.send("The bot is not installed in any servers.")
        return
    lines = []
    now = datetime.now(timezone.utc)
    for guild in bot.guilds[:20]:
        if guild.id == MAIN_SERVER_ID:
            age = "permanent main server"
        else:
            joined_at = server_join_times.get(guild.id)
            age = f"{(now - joined_at).days} days" if joined_at else "tracking starts now"
        lines.append(f"`{guild.id}` — **{guild.name}** ({age})")
    embed = discord.Embed(title="Bot servers", description="\n".join(lines), color=discord.Color.blurple())
    if len(bot.guilds) > 20:
        embed.set_footer(text=f"Showing 20 of {len(bot.guilds)} servers")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="server_age", description="Show how long the bot has been in a server")
async def server_age(ctx: commands.Context, server_id: str | None = None) -> None:
    guild = bot.get_guild(int(server_id)) if server_id else ctx.guild
    if not guild:
        await ctx.send("The bot is not in that server, or this command was used outside a server.")
        return
    if guild.id == MAIN_SERVER_ID:
        await ctx.send(f"**{guild.name}** is configured as the permanent main server.")
        return
    joined_at = server_join_times.setdefault(guild.id, datetime.now(timezone.utc))
    age = datetime.now(timezone.utc) - joined_at
    remaining = max(0, LEAVE_AFTER_DAYS - age.days)
    await ctx.send(
        f"**{guild.name}** has been tracked for **{age.days} days**. "
        f"Automatic departure in approximately **{remaining} days**."
    )


@bot.hybrid_command(name="invite", description="Generate a least-privilege bot invite link")
async def invite(ctx: commands.Context) -> None:
    client_id = bot.user.id if bot.user else None
    if not client_id:
        await ctx.send("The bot identity is not ready yet.")
        return
    url = discord.utils.oauth_url(client_id, permissions=discord.Permissions(view_channel=True, send_messages=True), scopes=("bot", "applications.commands"))
    await ctx.send(f"Invite the bot with least-privilege permissions: {url}")


@bot.hybrid_command(name="help", description="Show available commands")
async def show_help(ctx: commands.Context) -> None:
    embed = discord.Embed(title="Available commands", color=discord.Color.blurple())
    embed.add_field(name="!servers", value="List servers where the bot is installed.", inline=False)
    embed.add_field(name="!server_age [SERVER_ID]", value="Show tracking age and departure estimate.", inline=False)
    embed.add_field(name="!invite", value="Generate a least-privilege invite URL.", inline=False)
    embed.add_field(name="!help", value="Show this help message.", inline=False)
    embed.set_footer(text="This bot never requests, stores, refreshes, or transfers user access tokens.")
    await ctx.send(embed=embed)


if __name__ == "__main__":
    try:
        bot.run(BOT_TOKEN)
    except KeyboardInterrupt:
        pass
    finally:
        if not bot.is_closed():
            asyncio.run(bot.close())
