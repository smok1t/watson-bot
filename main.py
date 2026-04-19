import os
import re
import json
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
APPLICATION_CHANNEL_ID = int(os.getenv("APPLICATION_CHANNEL_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

FRIENDS_ROLE_ID = int(os.getenv("FRIENDS_ROLE_ID", "0"))
RECRUITER_ROLE_ID = int(os.getenv("RECRUITER_ROLE_ID", "0"))
FAMILY_ROLE_ID = int(os.getenv("FAMILY_ROLE_ID", "0"))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", "0"))

FAMILY_NAME = os.getenv("FAMILY_NAME", "WATSON")
BOT_NAME = os.getenv("BOT_NAME", "WATSON BOT")
PANEL_IMAGE_URL = os.getenv("PANEL_IMAGE_URL", "")
TICKETS_CATEGORY_NAME = os.getenv("TICKETS_CATEGORY_NAME", "📨・заявки-watson")

COUNTER_FILE = "ticket_counter.json"

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def main_color() -> discord.Color:
    return discord.Color.from_rgb(28, 28, 40)


def load_counter() -> int:
    if not os.path.exists(COUNTER_FILE):
        return 0

    try:
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return int(data.get("last_ticket_number", 0))
    except (json.JSONDecodeError, ValueError, OSError):
        return 0


def save_counter(value: int) -> None:
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_ticket_number": value}, f, ensure_ascii=False, indent=2)


def get_next_ticket_number() -> int:
    current = load_counter() + 1
    save_counter(current)
    return current


async def send_log(guild: discord.Guild, text: str):
    if LOG_CHANNEL_ID == 0:
        return

    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(text)


async def get_or_create_tickets_category(guild: discord.Guild) -> discord.CategoryChannel:
    category = discord.utils.get(guild.categories, name=TICKETS_CATEGORY_NAME)
    if category:
        return category

    recruiter_role = guild.get_role(RECRUITER_ROLE_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True,
            read_message_history=True,
            embed_links=True,
            attach_files=True,
        ),
    }

    if recruiter_role:
        overwrites[recruiter_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            read_message_history=True,
            embed_links=True,
            attach_files=True,
        )

    category = await guild.create_category(
        name=TICKETS_CATEGORY_NAME,
        overwrites=overwrites,
        reason="Автоматическое создание категории для тикетов"
    )

    await send_log(guild, f"📂 Бот автоматически создал категорию тикетов: **{category.name}**")
    return category


def build_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title=f"Подать заявку в {FAMILY_NAME}",
        description=(
            "Открыты заявки на вступление в семью!\n"
            "> 📌 **Заявки в семью принимаются только на сервер REDWOOD.**\n"
            "> **ВОЗРАСТ ДЛЯ РАССМОТРЕНИЯ ЗАЯВКИ: ОТ 14 ЛЕТ**\n\n"
            "**Срок рассмотрения заявок:** от начала создания заявки до 2х дней.\n"
            "Отсутствие ответа в тикете в течении 24 часов приводит к автоматическому закрытию тикета и повторной подаче в случае вашей необходимости.\n\n"
            "**Внимательно прочитайте шаблон заявки при её подаче.**\n\n"
            "> 📌 После подачи заявки следите за сообщениями в тикете, чтобы не пропустить нужную информацию.\n"

            "> После попадания на обзвоны вы автоматически соглашаетесь пройти проверку компьютера на сторонний софт и нарушения Правил Проекта."
        ),
        color=main_color()
    )
    if PANEL_IMAGE_URL:
        embed.set_image(url=PANEL_IMAGE_URL)
    embed.set_footer(text=f"{BOT_NAME} • Нажмите кнопку ниже, чтобы подать заявку")
    return embed


def build_ticket_header_embed(user: discord.Member, ticket_number: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"📨 Тикет #{ticket_number:04d} • {FAMILY_NAME}",
        description=(
            f"{user.mention}, ваше заявление успешно создано.\n"
            "Следите за сообщениями в этом тикете и в личных сообщениях.\n"
            "Рекрутер свяжется с вами здесь."
        ),
        color=main_color()
    )
    embed.add_field(
        name="Дальнейшие действия",
        value=(
            "• Ожидайте ответа рекрутера\n"
            "• Не игнорируйте пинг и ЛС\n"
            "• На обзвон зовут только в Discord\n"
            "• При долгом отсутствии ответа тикет может быть закрыт"
        ),
        inline=False
    )
    embed.set_footer(text=f"{BOT_NAME} • Тикет создан")
    return embed


def build_application_embed(user: discord.Member, ticket_number: int, form_data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📝 Заявление #{ticket_number:04d} в {FAMILY_NAME}",
        description=f"**Автор:** {user.mention}",
        color=main_color()
    )
    embed.add_field(name="Ваше имя и фамилия", value=form_data["full_name"], inline=False)
    embed.add_field(name="Ваш возраст", value=form_data["age"], inline=False)
    embed.add_field(name="В каких семьях находились ранее?", value=form_data["previous_families"], inline=False)
    embed.add_field(name="Откуда узнали о семье?", value=form_data["source_info"], inline=False)
    embed.add_field(name="Готовы пройти обзвон?", value=form_data["interview_ready"], inline=False)
    embed.add_field(name="Имеется ли возможность сменить фамилию?", value=form_data["surname_change"], inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"{BOT_NAME} • ID пользователя: {user.id}")
    return embed


class StaffButtons(View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        recruiter_role = interaction.guild.get_role(RECRUITER_ROLE_ID)
        if recruiter_role is None or recruiter_role not in interaction.user.roles:
            await interaction.response.send_message("Нет прав!", ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label="Принять заявление",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="watson_accept_application"
    )
    async def accept_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)

        if member is None:
            await interaction.response.send_message("Пользователь не найден на сервере.", ephemeral=True)
            return

        friends_role = guild.get_role(FRIENDS_ROLE_ID)
        family_role = guild.get_role(FAMILY_ROLE_ID)

        try:
            if friends_role and friends_role in member.roles:
                await member.remove_roles(friends_role, reason=f"Принят в {FAMILY_NAME}")

            if family_role:
                await member.add_roles(family_role, reason=f"Принят в {FAMILY_NAME}")

            embed = discord.Embed(
                title="✅ Заявление принято",
                description=f"{member.mention} принят в **{FAMILY_NAME}**.\nМодератор: {interaction.user.mention}",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"{BOT_NAME} • Принято")

            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("Заявление принято.", ephemeral=True)

            try:
                await member.send(
                    f"✅ Ваше заявление в **{FAMILY_NAME}** было принято.\n"
                    "Ожидайте дальнейших инструкций от рекрутера."
                )
            except discord.Forbidden:
                pass

            await send_log(guild, f"✅ {interaction.user.mention} принял заявление пользователя {member.mention}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "Бот не может выдать или снять роль. Проверь права и порядок ролей.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Отклонить заявление",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="watson_decline_application"
    )
    async def decline_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)

        embed = discord.Embed(
            title="❌ Заявление отклонено",
            description=f"Пользователь <@{self.applicant_id}> получил отказ.\nМодератор: {interaction.user.mention}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"{BOT_NAME} • Отклонено")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Заявление отклонено.", ephemeral=True)

        if member:
            try:
                await member.send(
                    f"❌ Ваше заявление в **{FAMILY_NAME}** было отклонено.\n"
                    "Позже вы сможете подать его заново."
                )
            except discord.Forbidden:
                pass

        await send_log(guild, f"❌ {interaction.user.mention} отклонил заявление пользователя <@{self.applicant_id}>")

    @discord.ui.button(
        label="Закрыть тикет",
        style=discord.ButtonStyle.secondary,
        emoji="📁",
        custom_id="watson_close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Тикет будет закрыт через 5 секунд.", ephemeral=True)
        await send_log(interaction.guild, f"📁 {interaction.user.mention} закрыл тикет {interaction.channel.name}")
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(
        label="Позвать в войс",
        style=discord.ButtonStyle.primary,
        emoji="📞",
        custom_id="watson_call_voice"
    )
    async def call_to_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        voice_channel = guild.get_channel(VOICE_CHANNEL_ID)

        if member is None:
            await interaction.response.send_message("Пользователь не найден.", ephemeral=True)
            return

        if voice_channel is None:
            await interaction.response.send_message("Войс-канал не найден.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📞 Вызов на обзвон",
            description=f"{member.mention}, вас вызывает {interaction.user.mention} в {voice_channel.mention}.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"{BOT_NAME} • Вызов в войс")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Пользователь вызван в войс.", ephemeral=True)

        try:
            await member.send(
                f"📞 Вас вызывают на обзвон в Discord **{FAMILY_NAME}**.\n"
                f"Голосовой канал: **{voice_channel.name}**"
            )
        except discord.Forbidden:
            pass

        await send_log(guild, f"📞 {interaction.user.mention} вызвал в войс пользователя {member.mention}")


class ApplicationModal(Modal, title="Форма заявления"):
    full_name = TextInput(
        label="Ваше имя и фамилия",
        placeholder="Введите имя и фамилию",
        required=True,
        max_length=100
    )

    age = TextInput(
        label="Ваш возраст",
        placeholder="Например: 18",
        required=True,
        max_length=3
    )

    previous_families = TextInput(
        label="В каких семьях находились ранее?",
        placeholder="Укажите семьи, в которых были ранее",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    source_info = TextInput(
        label="Откуда узнали о семье?",
        placeholder="Напишите, откуда узнали о семье",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    extra_info = TextInput(
        label="Обзвон / смена фамилии",
        placeholder="Например: Готов пройти обзвон, фамилию сменить могу",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        recruiter_role = guild.get_role(RECRUITER_ROLE_ID)

        category = await get_or_create_tickets_category(guild)

        existing_channel = None
        for channel in guild.text_channels:
            if channel.topic == str(user.id):
                existing_channel = channel
                break

        if existing_channel:
            await interaction.response.send_message(
                f"У вас уже есть открытый тикет: {existing_channel.mention}",
                ephemeral=True
            )
            return

        ticket_number = get_next_ticket_number()
        ticket_name = f"ticket-{ticket_number:04d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )
        }

        if recruiter_role:
            overwrites[recruiter_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        ticket_channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=str(user.id),
            reason=f"Новая заявка #{ticket_number:04d} от {user}"
        )

        embed = discord.Embed(
            title=f"📝 Заявление #{ticket_number:04d} в {FAMILY_NAME}",
            description=f"**Автор:** {user.mention}",
            color=main_color()
        )
        embed.add_field(name="Ваше имя и фамилия", value=self.full_name.value, inline=False)
        embed.add_field(name="Ваш возраст", value=self.age.value, inline=False)
        embed.add_field(name="В каких семьях находились ранее?", value=self.previous_families.value, inline=False)
        embed.add_field(name="Откуда узнали о семье?", value=self.source_info.value, inline=False)
        embed.add_field(name="Обзвон / смена фамилии", value=self.extra_info.value, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"{BOT_NAME} • ID пользователя: {user.id}")

        header_embed = build_ticket_header_embed(user, ticket_number)
        buttons_view = StaffButtons(applicant_id=user.id)

        ping_text = recruiter_role.mention if recruiter_role else "Рекрутеры не назначены"

        await ticket_channel.send(content=ping_text, embed=header_embed)
        await ticket_channel.send(embed=embed, view=buttons_view)

        try:
            await user.send(
                f"📨 Ваш тикет для заявки в **{FAMILY_NAME}** создан.\n"
                f"Номер: **#{ticket_number:04d}**\n"
                f"Сервер: **{guild.name}**\n"
                f"Канал: **#{ticket_channel.name}**"
            )
        except discord.Forbidden:
            pass

        await send_log(
            guild,
            f"📨 Создан тикет **#{ticket_number:04d}** {ticket_channel.mention} для пользователя {user.mention}"
        )

        await interaction.response.send_message(
            f"✅ Ваша заявка отправлена. Создан тикет: {ticket_channel.mention}",
            ephemeral=True
        )


class OpenApplicationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку в WATSON",
        style=discord.ButtonStyle.success,
        emoji="🖤",
        custom_id="watson_open_application"
    )
    async def open_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal())


@bot.event
async def on_ready():
    bot.add_view(OpenApplicationView())
    print(f"{BOT_NAME} запущен как {bot.user}")


@bot.event
async def on_member_join(member: discord.Member):
    role = member.guild.get_role(FRIENDS_ROLE_ID)
    if role:
        try:
            await member.add_roles(role, reason="Автовыдача роли Friends")
            await send_log(member.guild, f"👋 Пользователю {member.mention} автоматически выдана роль {role.mention}")
        except discord.Forbidden:
            print("Бот не может выдать роль Friends. Проверь права и иерархию ролей.")


@bot.command()
@commands.has_permissions(administrator=True)
async def panel(ctx: commands.Context):
    if ctx.guild is None:
        return

    if ctx.guild.id != GUILD_ID:
        await ctx.send("Эта команда не для этого сервера.")
        return

    if ctx.channel.id != APPLICATION_CHANNEL_ID:
        await ctx.send("Эту команду можно использовать только в канале подачи заявок.")
        return

    await ctx.send(embed=build_panel_embed(), view=OpenApplicationView())


@panel.error
async def panel_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для этой команды.")


if not TOKEN:
    raise ValueError("TOKEN не найден в .env")

bot.run(TOKEN)