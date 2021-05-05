import random
from contextlib import suppress
import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.constants import *
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.buff_id import BuffId
from sc2.ids.ability_id import AbilityId
from sc2.player import Bot, Computer


# on_step does the "await" functions EVERY STEP OF THE GAME

class Freshbot(sc2.BotAI):
    def __init__(self):
        self.queensAssignedHatcheries = {}  # queen:hatch key:value pairs for larva injecting
        self.queenLimit = 8

    # super basic target enemy main base or seen structures, MAKE BETTER!!
    def select_target(self) -> Point2:
        if self.enemy_structures:
            return random.choice(self.enemy_structures).position
        return self.enemy_start_locations[0]

    async def on_step(self, iteration):
        larvae: Units = self.larva
        forces: Units = self.units.of_type({UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.RAVAGER})

        if iteration == 0:
            await self.chat_send("Freshbot as designed by Freshpbj")

        # send all idle forces to attack if we have more than 8 ling/roach/ravager, might need to bump it up
        if forces.amount > 8 and iteration % 50 == 0:
            for unit in forces.idle:
                unit.attack(self.select_target())

# don't get supply blocked, but don't waste minerals on overlords above supply cap
        if (
            self.supply_left < 3
            and self.supply_cap < 200
            and self.already_pending(UnitTypeId.OVERLORD) < 2
            and self.can_afford(UnitTypeId.OVERLORD)
        ):
            self.train(UnitTypeId.OVERLORD)
        # build enough drones to fully saturate a base
        if self.can_afford(UnitTypeId.DRONE) and self.supply_workers < self.townhalls.amount * 20:
            self.train(UnitTypeId.DRONE)

        await self.distribute_workers()

# make building and expansion logic here
        # Expand if we have 300 minerals, try to expand if there is one more expansion location available
        if self.townhalls.amount < 2 and self.workers.amount > 16:
            location = await self.get_next_expansion()
            loc = await self.find_placement(UnitTypeId.HATCHERY, near=location, random_alternative=False, placement_step=1, max_distance=20)
            if loc is not None:
                await self.expand_now(building=UnitTypeId.HATCHERY, max_distance=10, location=loc)

        if self.can_afford(UnitTypeId.SPAWNINGPOOL) and self.already_pending(
                UnitTypeId.SPAWNINGPOOL) + self.structures.filter(
                lambda structure: structure.type_id == UnitTypeId.SPAWNINGPOOL and structure.is_ready).amount == 0:
            map_center = self.game_info.map_center
            position_towards_map_center = self.start_location.towards(map_center, distance=5)
            await self.build(UnitTypeId.SPAWNINGPOOL, near=position_towards_map_center, placement_step=1)

        if (
            self.can_afford(UnitTypeId.QUEEN)
            and not self.already_pending(UnitTypeId.QUEEN)
            and len(self.units.of_type(UnitTypeId.QUEEN)) < self.townhalls.amount + 2
            and self.structures(UnitTypeId.SPAWNINGPOOL).ready
        ):
            self.train(UnitTypeId.QUEEN)

        # currently sends all queens together to each hatch, FIX THIS
        for queen in self.units(UnitTypeId.QUEEN).idle:
            hq: Unit = self.townhalls.first
            if queen.energy >= 25 and not hq.has_buff(BuffId.QUEENSPAWNLARVATIMER):
                queen(AbilityId.EFFECT_INJECTLARVA, hq)

# macro/economy stuff here

# CREEP SPREAD, make this do some crazy shit and spread creep across the entire map

# scouting, need to know what to build before we build it!

# use knowledge from scouting to build defense / offense to counter enemy

# make a basic build in case scouting failed / didn't get enough info


# maps are at E://DiabloTre/StarCraftII/Maps/
run_game(maps.get("AutomatonLE"), [
    Bot(Race.Zerg, Freshbot()),
    Computer(Race.Protoss, Difficulty.Easy)
], realtime=True)