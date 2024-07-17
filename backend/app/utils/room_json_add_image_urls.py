import json


def update_rooms_with_images(rooms):
    for room in rooms:
        room["images"] = {}
        sizes = list(range(room["size_min"], room["size_max"] + 1, room["size_min"]))

        if room.get("t2_upgrade_cost"):
            room["images"]["tier1"] = {
                f"size{size}": f"url_to_image_for_{room['name']}_tier1_size{size}" for size in sizes
            }
            room["images"]["tier2"] = {
                f"size{size}": f"url_to_image_for_{room['name']}_tier2_size{size}" for size in sizes
            }
        if room.get("t3_upgrade_cost"):
            room["images"]["tier3"] = {
                f"size{size}": f"url_to_image_for_{room['name']}_tier3_size{size}" for size in sizes
            }

    return rooms


# Read the JSON file
with open("../../data/vault/rooms.json") as file:
    rooms = json.load(file)

# Update the rooms
updated_rooms = update_rooms_with_images(rooms)

# Write the updated rooms back to the JSON file
with open("../../data/vault/updated_rooms.json", "w") as file:
    json.dump(updated_rooms, file, indent=2)

print("Rooms updated and saved to 'updated_rooms.json'")
