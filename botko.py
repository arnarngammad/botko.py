        except discord.NotFound:
            # The user deleted the panel message.
            expired_message_ids.append(message_id)
        except discord.Forbidden:
            # The bot can no longer edit this message.
            expired_message_ids.append(message_id)
        except discord.HTTPException as e:
            # Keep tracking the panel for transient API errors/rate limits.
            print(f"❌ Farm panel auto-countdown edit failed: {e}")

    for message_id in expired_message_ids:
        FARM_PANEL_MESSAGES.pop(message_id, None)


@farm_panel_update_loop.before_loop
async def before_farm_panel_update_loop():
    await bot.wait_until_ready()


@tasks.loop(seconds=10)
async def farm_timer_loop():
    try:
        now = time.time()
        conn = get_spam_db()
        rows = conn.execute(
            "SELECT * FROM farm_entries WHERE end_time IS NOT NULL AND end_time <= ?",
            (now,)
        ).fetchall()
        conn.close()

        for row in rows:
            user_id = row["user_id"]
            world = row["world"]
            farm_type = row["farm_type"]
            info = FARM_TIMERS.get(farm_type)
            if not info:
                continue

            farm_set_end(user_id, world, farm_type, None)
            try:
                user = await bot.fetch_user(user_id)
                await user.send(
                    f"{info['emoji']} Your farm **{world}** — "
                    f"**{info['label']}** is ready!"
                )
            except discord.Forbidden:
                # DMs closed: ping in channel WITHOUT revealing the world name
                channel = bot.get_channel(SPAM_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"{info['emoji']} <@{user_id}> one of your "
                        f"**{info['label']}** timers is ready! (Use `/farm`)",
                        delete_after=60
                    )
            except Exception as e:
                print(f"❌ Farm ping error: {e}")
    except Exception as e:
        print(f"❌ Farm timer loop error: {e}")

@farm_timer_loop.before_loop
async def before_farm_timer_loop():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print("===================================")
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("===================================")

    initialize_spam_database()
    initialize_farm_database()          # <-- NEW

    if not hasattr(bot, "_spam_view_registered"):
        bot.add_view(SpamView())
        bot._spam_view_registered = True
        print("Persistent Spam panel registered.")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Slash command sync error: {e}")

    if not spam_timer_loop.is_running():
        spam_timer_loop.start()
        print("Spam timer loop started.")

    if not farm_timer_loop.is_running():    # <-- NEW
        farm_timer_loop.start()
        print("Farm timer loop started.")

    if not farm_panel_update_loop.is_running():
        farm_panel_update_loop.start()
        print("Farm panel live countdown updater started.")

    await update_spam_panel()

    print("📢 Spam system is running!")
    print("🌾 Farm system is running!")
    print("===================================")

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        raise RuntimeError("TOKEN environment variable is missing.")
    keep_alive()
    bot.run(token)
