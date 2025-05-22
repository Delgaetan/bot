import os
import sqlite3
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from discord import Embed

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = "your token"
DB_PATH = "data/bot.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Crée la table users si elle n'existe pas
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            last_pack TIMESTAMP
        )''')

        # Ajoute la colonne coins si elle n'existe pas
        try:
            c.execute("ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            # La colonne existe déjà
            pass

        # Autres tables
        c.execute('''CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rarity TEXT,
            hp INTEGER,
            attack INTEGER,
            defense INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_cards (
            user_id INTEGER,
            card_id INTEGER,
            FOREIGN KEY(card_id) REFERENCES cards(id)
        )''')
        conn.commit()




active_battles = {}

@bot.tree.command(name="duel", description="Défie un joueur en combat de cartes")
@app_commands.describe(opponent="Le joueur que tu veux défier")
async def duel_command(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        return await interaction.response.send_message("Tu ne peux pas te défier toi-même !", ephemeral=True)

    if interaction.user.id in active_battles or opponent.id in active_battles:
        return await interaction.response.send_message("Un des deux joueurs est déjà en combat.", ephemeral=True)

    await interaction.response.send_message(f"{opponent.mention}, {interaction.user.name} te défie ! Acceptes-tu ? (Réponds avec `!accept`)", ephemeral=False)
    active_battles[interaction.user.id] = {"opponent": opponent.id, "status": "pending"}




@bot.command(name="accept")
async def accept_duel(ctx):
    user_id = ctx.author.id
    for challenger_id, data in active_battles.items():
        if data["opponent"] == user_id and data["status"] == "pending":
            active_battles[challenger_id]["status"] = "choosing"
            active_battles[challenger_id]["challenger_card"] = None
            active_battles[challenger_id]["opponent_card"] = None
            await ctx.send(f"<@{challenger_id}> et <@{user_id}> : Choisissez une carte avec `/choosecard id:NUM`", mention_author=True)
            return
    await ctx.send("Tu n'as aucun duel à accepter.", mention_author=True)


@bot.tree.command(name="choosecard", description="Choisis une carte pour le duel")
@app_commands.describe(id="ID de ta carte")
async def choose_card(interaction: discord.Interaction, id: int):
    user_id = interaction.user.id
    battle = None
    for cid, data in active_battles.items():
        if cid == user_id or data.get("opponent") == user_id:
            battle = (cid, data)
            break
    if not battle:
        return await interaction.response.send_message("Tu n'es dans aucun combat.", ephemeral=True)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''SELECT cards.id, name, hp, attack, defense FROM cards
                     JOIN user_cards ON cards.id = user_cards.card_id
                     WHERE cards.id = ? AND user_cards.user_id = ?''', (id, user_id))
        card = c.fetchone()
        if not card:
            return await interaction.response.send_message("Carte invalide ou ne t'appartient pas.", ephemeral=True)

    cid, data = battle
    if user_id == cid:
        data["challenger_card"] = list(card)
    else:
        data["opponent_card"] = list(card)

    await interaction.response.send_message(f"✅ Carte choisie : {card[1]} (HP: {card[2]}, ATK: {card[3]}, DEF: {card[4]})", ephemeral=True)

    if data["challenger_card"] and data["opponent_card"]:
        await launch_battle(interaction, cid, data)


async def launch_battle(interaction, challenger_id, data):
    user1 = challenger_id
    user2 = data["opponent"]
    card1 = data["challenger_card"]
    card2 = data["opponent_card"]

    hp1, atk1, def1 = card1[2], card1[3], card1[4]
    hp2, atk2, def2 = card2[2], card2[3], card2[4]

    turn = 0
    log = f"⚔️ **Combat entre <@{user1}> et <@{user2}> !**\n\n"
    while hp1 > 0 and hp2 > 0:
        attacker = user1 if turn % 2 == 0 else user2
        defender = user2 if turn % 2 == 0 else user1
        atk = atk1 if turn % 2 == 0 else atk2
        def_ = def2 if turn % 2 == 0 else def1

        damage = max(1, atk - def_)
        if turn % 2 == 0:
            hp2 -= damage
            log += f"👉 <@{user1}> attaque : -{damage} HP à <@{user2}> ({max(hp2,0)} restants)\n"
        else:
            hp1 -= damage
            log += f"👈 <@{user2}> riposte : -{damage} HP à <@{user1}> ({max(hp1,0)} restants)\n"
        turn += 1

    winner = user1 if hp1 > 0 else user2
    loser = user2 if winner == user1 else user1

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET coins = coins + 10 WHERE user_id = ?", (winner,))
        conn.commit()

    log += f"\n🏆 <@{winner}> remporte le combat et gagne **10 coins** !"
    del active_battles[user1]
    channel = interaction.channel
    await channel.send(log)


@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Synced commands.")

@bot.tree.command(name="duel_leave", description="Quitte un duel en cours.")
async def duel_leave(interaction: discord.Interaction):
    user_id = interaction.user.id

    # Recherche dans active_battles si le joueur est un challenger ou un opposant
    to_remove = None
    for challenger_id, data in active_battles.items():
        if challenger_id == user_id or data.get("opponent") == user_id:
            to_remove = challenger_id
            break

    if to_remove:
        del active_battles[to_remove]
        await interaction.response.send_message("🚪 Vous avez quitté le duel en cours.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Vous n'êtes dans aucun duel.", ephemeral=True)



@bot.tree.command(name="pack", description="Ouvre un pack de cartes (1 pack toutes les 3h)")
async def pack_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.now(timezone.utc)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Vérifie si l'utilisateur existe déjà
        c.execute("SELECT last_pack FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if not row:
            # Nouvel utilisateur, on l'ajoute
            c.execute("INSERT INTO users (user_id, last_pack) VALUES (?, ?)", (user_id, now - timedelta(hours=3)))
            conn.commit()
            last_time = now - timedelta(hours=3)
        else:
            last_time = datetime.fromisoformat(row[0]) if row[0] else now - timedelta(hours=3)

        # Vérifie le cooldown
        if now - last_time < timedelta(hours=3):
            remaining = timedelta(hours=3) - (now - last_time)
            mins = int(remaining.total_seconds() // 60)
            return await interaction.response.send_message(
                f"⏳ Tu dois attendre encore {mins} min avant de reprendre un pack.", ephemeral=True)

        # Donne les cartes
        c.execute("SELECT id, name, rarity, hp, attack, defense FROM cards ORDER BY RANDOM() LIMIT 3")
        cards = c.fetchall()
        for card in cards:
            c.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user_id, card[0]))

        # Met à jour le cooldown
        c.execute("UPDATE users SET last_pack = ? WHERE user_id = ?", (now.isoformat(), user_id))
        conn.commit()

        message = "🎁 Tu as reçu les cartes suivantes :\n\n"
        for card in cards:
            message += (
                f"🃏 **{card[1]}** (#{card[0]})\n"
                f"   Rareté: {card[2]}\n"
                f"   HP: {card[3]} | ATK: {card[4]} | DEF: {card[5]}\n\n"
            )
        await interaction.response.send_message(message, ephemeral=True)





class DeckPaginator(View):
    def __init__(self, pages, user_id):
        super().__init__(timeout=60)
        self.pages = pages
        self.page = 0
        self.user_id = user_id

    async def update_message(self, interaction):
        embed = Embed(title="📚 Ton deck", color=0x00ff00)
        for card in self.pages[self.page]:
            embed.add_field(
                name=f"Carte #{card[0]} - {card[1]}",
                value=f"Rareté: {card[2]}\nHP: {card[3]}\nATK: {card[4]}\nDEF: {card[5]}",
                inline=False
            )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
        if self.page < len(self.pages) - 1:
            self.page += 1
            await self.update_message(interaction)

@bot.tree.command(name="deck", description="Affiche tes cartes")
async def deck_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''SELECT cards.id, cards.name, cards.rarity, cards.hp, cards.attack, cards.defense FROM cards
                     JOIN user_cards ON cards.id = user_cards.card_id
                     WHERE user_cards.user_id = ?''', (user_id,))
        cards = c.fetchall()

    if not cards:
        return await interaction.response.send_message("🃏 Tu n'as aucune carte.", ephemeral=True)

    pages = [cards[i:i+10] for i in range(0, len(cards), 10)]
    embed = Embed(title="📚 Ton deck", color=0x00ff00)
    for card in pages[0]:
        embed.add_field(
            name=f"Carte #{card[0]} - {card[1]}",
            value=f"Rareté: {card[2]}\nHP: {card[3]}\nATK: {card[4]}\nDEF: {card[5]}",
            inline=False
        )

    view = DeckPaginator(pages, user_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



from discord import app_commands
from discord.ui import View, Button
import asyncio

@bot.tree.command(name="trade", description="Propose un échange de cartes à un autre joueur.")
@app_commands.describe(carte_id_toi="L'ID de ta carte", carte_id_lui="L'ID de la carte de l'autre joueur")
async def trade(interaction: discord.Interaction, joueur: discord.User, carte_id_toi: int, carte_id_lui: int):
    user_id = interaction.user.id
    target_id = joueur.id

    if user_id == target_id:
        return await interaction.response.send_message("❌ Tu ne peux pas échanger avec toi-même.", ephemeral=True)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Vérifie que l'utilisateur possède bien la carte
        c.execute("SELECT * FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, carte_id_toi))
        if not c.fetchone():
            return await interaction.response.send_message("❌ Tu ne possèdes pas cette carte.", ephemeral=True)

        # Vérifie que l'autre joueur possède bien sa carte
        c.execute("SELECT * FROM user_cards WHERE user_id = ? AND card_id = ?", (target_id, carte_id_lui))
        if not c.fetchone():
            return await interaction.response.send_message("❌ L'autre joueur ne possède pas cette carte.", ephemeral=True)

    # Envoie une demande de confirmation à l'autre joueur
    class TradeConfirm(View):
        def __init__(self):
            super().__init__(timeout=30)
            self.value = None

        @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.green)
        async def accept(self, interaction_b: discord.Interaction, button: Button):
            if interaction_b.user.id != target_id:
                return await interaction_b.response.send_message("❌ Tu n'es pas concerné par cet échange.", ephemeral=True)
            self.value = True
            self.stop()
            await interaction_b.response.send_message("✅ Échange accepté !", ephemeral=True)

        @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.red)
        async def reject(self, interaction_b: discord.Interaction, button: Button):
            if interaction_b.user.id != target_id:
                return await interaction_b.response.send_message("❌ Tu n'es pas concerné par cet échange.", ephemeral=True)
            self.value = False
            self.stop()
            await interaction_b.response.send_message("❌ Échange refusé.", ephemeral=True)

    view = TradeConfirm()
    await interaction.response.send_message(
        f"{joueur.mention}, {interaction.user.mention} te propose un échange :\n"
        f"🃏 Sa carte ID `{carte_id_toi}` contre ta carte ID `{carte_id_lui}`.\n"
        f"Accepte ou refuse ci-dessous 👇",
        view=view
    )

    timeout = await view.wait()
    if view.value:
        # Échange les cartes
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE user_cards SET user_id = ? WHERE user_id = ? AND card_id = ?", (target_id, user_id, carte_id_toi))
            c.execute("UPDATE user_cards SET user_id = ? WHERE user_id = ? AND card_id = ?", (user_id, target_id, carte_id_lui))
            conn.commit()
        await interaction.followup.send("🔄 Échange complété avec succès !", ephemeral=True)
    elif view.value is False:
        await interaction.followup.send("ℹ️ L'échange a été annulé.", ephemeral=True)
    else:
        await interaction.followup.send("⌛ Temps écoulé, l'échange a été annulé.", ephemeral=True)


@bot.tree.command(name="shop", description="Affiche les cartes disponibles à l'achat.")
async def shop(interaction: discord.Interaction):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, rarity, hp, attack, defense, price FROM cards ORDER BY price ASC LIMIT 10")
        cards = c.fetchall()

    embed = discord.Embed(title="🛒 Boutique de cartes", description="Voici les cartes que tu peux acheter :", color=0xFFD700)
    for card in cards:
        embed.add_field(
            name=f"Carte #{card[0]} - {card[1]} ({card[2]})",
            value=f"HP: {card[3]}, ATK: {card[4]}, DEF: {card[5]}\n💰 Prix : {card[6]} coins\n➤ `/buy {card[0]}`",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@bot.tree.command(name="buy", description="Achète une carte avec tes coins.")
@app_commands.describe(card_id="L'ID de la carte que tu veux acheter")
async def buy(interaction: discord.Interaction, card_id: int):
    user_id = interaction.user.id

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Récupère les infos carte
        c.execute("SELECT name, price FROM cards WHERE id = ?", (card_id,))
        result = c.fetchone()
        if not result:
            return await interaction.response.send_message("❌ Cette carte n'existe pas.", ephemeral=True)

        card_name, price = result

        # Vérifie le solde du joueur
        c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return await interaction.response.send_message("❌ Ton profil est introuvable.", ephemeral=True)

        coins = row[0]
        if coins < price:
            return await interaction.response.send_message("❌ Tu n'as pas assez de coins pour acheter cette carte.",
                                                           ephemeral=True)

        # Ajoute la carte et enlève les coins
        c.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, user_id))
        conn.commit()

    await interaction.response.send_message(f"✅ Tu as acheté la carte **{card_name}** pour **{price}** coins !",
                                            ephemeral=True)



@bot.tree.command(name="allcards", description="Affiche toutes les cartes disponibles.")
@app_commands.describe(order="Mode de tri : 'rarity' ou 'id'")
async def allcards(interaction: discord.Interaction, order: str = "rarity"):
    user_id = interaction.user.id

    # Connexion à la DB
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Vérifie si l'utilisateur a un profil
        c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))

        result = c.fetchone()
        if not result:
            return await interaction.response.send_message("❌ Tu n'as pas de profil.", ephemeral=True)
        user_coins = result[0]

        # Récupère toutes les cartes
        c.execute("SELECT id, name, rarity, hp, attack, defense, price FROM cards")
        cards = c.fetchall()

    if not cards:
        return await interaction.response.send_message("❌ Aucune carte disponible.", ephemeral=True)

    # Tri
    if order == "id":
        cards.sort(key=lambda x: x[0])
    else:
        rarity_order = {"Legendary": 0, "Epic": 1, "Rare": 2, "Common": 3}
        cards.sort(key=lambda x: rarity_order.get(x[2], 99))

    pages = [cards[i:i + 10] for i in range(0, len(cards), 10)]

    def create_embed(page_index):
        embed = discord.Embed(
            title="🗂️ Toutes les cartes disponibles",
            description=f"Page {page_index + 1}/{len(pages)} — Tri: `{order}`",
            color=discord.Color.blue()
        )
        for card in pages[page_index]:
            embed.add_field(
                name=f"#{card[0]} - {card[1]}",
                value=(
                    f"🌟 Rareté: {card[2]}\n"
                    f"❤️ HP: {card[3]} | 🗡 ATK: {card[4]} | 🛡 DEF: {card[5]}\n"
                    f"💰 Prix: {card[6]} coins"
                ),
                inline=False
            )
        return embed

    class CardShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.page = 0

        async def update_message(self, interaction):
            await interaction.response.edit_message(embed=create_embed(self.page), view=self)

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
        async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page -= 1
                await self.update_message(interaction)

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page < len(pages) - 1:
                self.page += 1
                await self.update_message(interaction)

        @discord.ui.button(label="🛒 Acheter une carte", style=discord.ButtonStyle.success)
        async def buy_card(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Ouvre un select menu des cartes de cette page
            options = []
            for card in pages[self.page]:
                label = f"{card[1]} ({card[6]} coins)"
                options.append(discord.SelectOption(label=label, value=str(card[0])))

            select = discord.ui.Select(placeholder="Choisis une carte à acheter", options=options)

            async def select_callback(interaction_: discord.Interaction):
                card_id = int(select.values[0])
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()

                    # Vérifie que la carte existe
                    c.execute("SELECT name, price FROM cards WHERE id = ?", (card_id,))
                    card = c.fetchone()
                    if not card:
                        return await interaction_.response.send_message("❌ Carte introuvable.", ephemeral=True)

                    name, price = card

                    # Vérifie les coins
                    c.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
                    coins = c.fetchone()[0]
                    if coins < price:
                        return await interaction_.response.send_message("❌ Pas assez de coins.", ephemeral=True)

                    # Déduit les coins et ajoute la carte
                    c.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (price, user_id))
                    c.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
                    conn.commit()

                await interaction_.response.send_message(f"✅ Tu as acheté **{name}** pour {price} coins !", ephemeral=True)

            select.callback = select_callback
            view = discord.ui.View()
            view.add_item(select)
            await interaction.response.send_message("Choisis une carte à acheter :", view=view, ephemeral=True)

    await interaction.response.send_message(embed=create_embed(0), view=CardShopView(), ephemeral=True)



@bot.tree.command(name="resetpack", description="(Admin) Réinitialise ton cooldown de pack")
async def reset_pack_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET last_pack = ? WHERE user_id = ?", (None, user_id))
        conn.commit()
    await interaction.response.send_message("✅ Ton cooldown a été réinitialisé. Tu peux reprendre un pack !", ephemeral=True)

bot.run(TOKEN)
