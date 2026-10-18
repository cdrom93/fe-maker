// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA struct ItemData gItemData[] = {
	[ITEM_NONE] = {
		.number = ITEM_NONE,
		.weaponType = ITYPE_SWORD,
		.iconId = 0x0,
	},
	[ITEM_TESTBLADE] = {
		.nameTextId = 0x4,
		.number = ITEM_TESTBLADE,
		.weaponType = ITYPE_SWORD,
		.attributes = IA_WEAPON | IA_LOCK_4,
		.maxUses = 20,
		.might = 3,
		.hit = 80,
		.weight = 4,
		.encodedRange = 0x12,
		.costPerUse = 7,
		.weaponRank = WPN_EXP_D,
		.iconId = 0x1,
		.pEffectiveness = ItemEffectiveness_TestKnights,
	},
};
