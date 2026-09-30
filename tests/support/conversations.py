"""Character-creation conversations for the four fixtures (J1 step 1)."""
BROM = ["new character",
        "A dwarf fighter, ex-soldier, standard array with Str 15, Dex 14, Con 13, Wis 10, Cha 12, Int 8. "
        "Put +2 in Strength and +1 in Constitution. Defense style. Chain mail, shield and longsword.",
        "His name is Brom", "lawful good", "He speaks Dwarvish and Giant", "Skills: perception and survival",
        "Weapon mastery with longsword, javelin and glaive",
        "Also buy a glaive, 4 javelins and a dungeoneer's pack", "He plays dice as his gaming set",
        "background package A", "done"]
LIDDA = ["new character",
         "A halfling rogue with the criminal background, named Lidda. Standard array: Str 12, Dex 15, Con 13, "
         "Int 14, Wis 10, Cha 8. +2 to Dexterity and +1 to Constitution.",
         "chaotic good", "She speaks Halfling, Elvish and Goblin",
         "Skills: acrobatics, deception, investigation and perception", "Expertise in stealth and sleight of hand",
         "Weapon mastery with shortsword and dagger", "class package A", "background package A",
         "Instead of a second thieves' tools she learns the disguise kit", "done"]
MIALEE = ["new character",
          "A high elf wizard called Mialee, a sage. Standard array: Str 8, Dex 12, Con 13, Int 15, Wis 14, Cha 10. "
          "+2 to Intelligence, +1 to Constitution.",
          "Her lineage spellcasting ability is Intelligence", "Keen senses: perception", "neutral good",
          "She speaks Elvish and Draconic", "Skills: investigation and medicine",
          "Cantrips: fire bolt, mage hand and light",
          "Magic initiate from the wizard list using intelligence: ray of frost, minor illusion and thunderwave",
          "Spellbook: magic missile, shield, sleep, burning hands, mage armor, detect magic",
          "Prepare magic missile, shield, sleep and mage armor", "class package A", "background package A", "done"]
JOZAN = ["new character",
         "A human cleric named Jozan, an acolyte, medium size. Standard array: Str 14, Dex 8, Con 13, Int 10, "
         "Wis 15, Cha 12. +2 Wisdom, +1 Charisma.",
         "lawful good", "He speaks Dwarvish and Halfling", "Skills: medicine and persuasion", "Divine order: protector",
         "Skillful: perception", "Versatile feat: skilled in athletics, survival and woodcarver's tools",
         "Magic initiate from the cleric list using wisdom: light, thaumaturgy and command",
         "Cantrips: sacred flame, guidance and spare the dying",
         "Prepare bless, cure wounds, healing word and guiding bolt", "class package A", "background package A", "done"]
ALL = {"BROM": BROM, "LIDDA": LIDDA, "MIALEE": MIALEE, "JOZAN": JOZAN}


def create_party(p):
    transcript = []
    for name, lines in ALL.items():
        for line in lines:
            transcript.append(("> " + line, p.say(line)))
    return transcript
