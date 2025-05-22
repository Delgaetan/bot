import sqlite3
import random

# Connexion à la base de données
conn = sqlite3.connect("data/bot.db")
c = conn.cursor()

# Ajouter la colonne 'price' si elle n'existe pas
try:
    c.execute("ALTER TABLE cards ADD COLUMN price INTEGER DEFAULT 100")
    print("✅ Colonne 'price' ajoutée.")
except sqlite3.OperationalError:
    print("ℹ️ La colonne 'price' existe déjà.")

def generate_cards():
    terraria_minecraft_names = [
        "Zombie", "Creeper", "Skeleton", "Enderman", "Slime", "Ghast", "Blaze", "Witch", "Spider", "Wither",
        "Herobrine", "Steve", "Alex", "Piglin", "Guardian", "Iron Golem", "Snow Golem", "Warden", "Glow Squid",
        "Phantom", "Villager", "Witch Doctor", "Eye of Cthulhu", "Brain of Cthulhu", "Eater of Worlds", "Skeletron",
        "The Twins", "The Destroyer", "Plantera", "Golem", "Duke Fishron", "Moon Lord", "King Slime", "Wall of Flesh",
        "Queen Bee", "Lunatic Cultist", "Goblin Tinkerer", "Demolitionist", "Nurse", "Guide", "Merchant", "Angler",
        "Clothier", "Cyborg", "Mechanic", "Painter", "Pirate", "Stylist", "Travelling Merchant"
    ]

    all_names = []
    while len(all_names) < 200:
        name = random.choice(terraria_minecraft_names)
        if name not in all_names or all_names.count(name) < 15:
            all_names.append(f"{name} Lv{random.randint(1, 100)}")

    rarities = ["Common", "Rare", "Epic", "Legendary"]
    stat_ranges = {
        "Common": {"hp": (50, 70), "attack": (10, 20), "defense": (5, 15), "price": 100},
        "Rare": {"hp": (70, 90), "attack": (20, 30), "defense": (15, 25), "price": 250},
        "Epic": {"hp": (90, 110), "attack": (30, 40), "defense": (25, 35), "price": 500},
        "Legendary": {"hp": (110, 130), "attack": (40, 50), "defense": (35, 45), "price": 1000}
    }

    for name in all_names:
        rarity = random.choices(rarities, weights=[60, 25, 10, 5])[0]
        stats = stat_ranges[rarity]
        hp = random.randint(*stats["hp"])
        attack = random.randint(*stats["attack"])
        defense = random.randint(*stats["defense"])
        price = stats["price"]

        c.execute(
            "INSERT INTO cards (name, rarity, hp, attack, defense, price) VALUES (?, ?, ?, ?, ?, ?)",
            (name, rarity, hp, attack, defense, price)
        )

    conn.commit()
    print("✅ 200 cartes Minecraft/Terraria générées avec succès.")

if __name__ == "__main__":
    generate_cards()
