import random
import cv2
import numpy as np
import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.constants import *
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.buff_id import BuffId
from sc2.ids.ability_id import AbilityId
from sc2.player import Bot, Computer


# on_step does the "await" functions EVERY STEP OF THE GAME
# TODO List - Make ravagers
# Creep spread
# expand to 3rd/4th bases
# get upgrades (burrow/zergling speed/attack/armor)
# nydus worm networking

class Freshbot(sc2.BotAI):
    def __init__(self):
        self.queensAssignedHatcheries = {}  # queen:hatch key:value pairs for larva injecting
        self.queenLimit = 8

    def assignQueenTag(self):
        if not hasattr(self, "queensAssignedHatcheries"):
            self.queensAssignedHatcheries = {}

        # if queen is done, move it to the closest hatch that doesnt have one assigned
        queensNoInjectPartner = self.units(UnitTypeId.QUEEN).filter(lambda q: q.tag not in self.queensAssignedHatcheries.keys())
        basesNoInjectPartner = self.townhalls.filter(lambda h: h.tag not in self.queensAssignedHatcheries.values())

        for queen in queensNoInjectPartner:
            if basesNoInjectPartner.amount == 0:
                break
            closestBase = basesNoInjectPartner.closest_to(queen)
            self.queensAssignedHatcheries[queen.tag] = closestBase.tag
            basesNoInjectPartner = basesNoInjectPartner - [closestBase]
            break  # else on hatch gets assigned twice

    async def doLarvaInjects(self):
        aliveQueenTags = [queen.tag for queen in self.units(UnitTypeId.QUEEN)]
        aliveBasesTags = [base.tag for base in self.townhalls]

        toRemoveTags = []

        if hasattr(self, "queensAssignedHatcheries"):
            for queenTag, hatchTag in self.queensAssignedHatcheries.items():
                # queen is no longer alive
                if queenTag not in aliveQueenTags:
                    toRemoveTags.append(queenTag)
                    continue
                # hatchery is no longer alive
                if hatchTag not in aliveBasesTags:
                    toRemoveTags.append(queenTag)
                    continue
                # queen and base are alive, try to inject if over 25 energy
                queen = self.units(UnitTypeId.QUEEN).find_by_tag(queenTag)
                hatch = self.townhalls.find_by_tag(hatchTag)
                if hatch.is_ready:
                    if queen.energy >= 25 and queen.is_idle and not hatch.has_buff(BuffId.QUEENSPAWNLARVATIMER):
                        queen(AbilityId.EFFECT_INJECTLARVA, hatch)
                    else:
                        if queen.is_idle and queen.position.distance_to(hatch.position) > 10:
                            queen(AbilityId.MOVE, hatch.position.to2)

            # clear tags in case of death/destruction to keep dictionary relevant
            for tag in toRemoveTags:
                self.queensAssignedHatcheries.pop(tag)

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

        # draw an opencv image for creep
        await self.intel()

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

        if larvae and self.can_afford(UnitTypeId.ZERGLING) and self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if self.units(UnitTypeId.ZERGLING).amount < 20:
                larvae.random.train(UnitTypeId.ZERGLING)

        if larvae and self.can_afford(UnitTypeId.ROACH) and self.structures(UnitTypeId.ROACHWARREN).ready:
            larvae.random.train(UnitTypeId.ROACH)

        # transform roaches into ravagers at a ratio (4ish?:1)

# make building and expansion logic here
        # Expand if we have 300 minerals, try to expand if there is one more expansion location available
        if self.townhalls.amount < 2 and self.workers.amount > 16 and self.can_afford(UnitTypeId.HATCHERY):
            location = await self.get_next_expansion()
            loc = await self.find_placement(UnitTypeId.HATCHERY, near=location, random_alternative=False, placement_step=1, max_distance=20)
            if loc is not None:
                await self.expand_now(building=UnitTypeId.HATCHERY, max_distance=10, location=loc)

        if self.townhalls.amount < 3 and self.supply_used >= 70 and self.can_afford(UnitTypeId.HATCHERY):
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

        if self.structures(UnitTypeId.SPAWNINGPOOL).exists:
            if self.can_afford(UnitTypeId.EXTRACTOR):
                vgs: Units = self.vespene_geyser.closer_than(20.0, self.townhalls.first)
                for vg in vgs:
                    if self.structures(UnitTypeId.EXTRACTOR).closer_than(1.0, vg).exists:
                        break

                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break
                    worker.build(UnitTypeId.EXTRACTOR, vg)
                    break

        if (
            self.can_afford(UnitTypeId.QUEEN)
            and not self.already_pending(UnitTypeId.QUEEN)
            and len(self.units.of_type(UnitTypeId.QUEEN)) < self.townhalls.amount + 2
            and self.structures(UnitTypeId.SPAWNINGPOOL).ready
        ):
            self.train(UnitTypeId.QUEEN)


# macro/economy stuff here
        if self.can_afford(UnitTypeId.ROACHWARREN):
            if not self.already_pending(UnitTypeId.ROACHWARREN) and not self.structures(UnitTypeId.ROACHWARREN).ready:
                map_center = self.game_info.map_center
                position_towards_map_center = self.start_location.towards(map_center, distance=5)
                await self.build(UnitTypeId.ROACHWARREN, near=position_towards_map_center, placement_step=1)
# CREEP SPREAD, make this do some crazy shit and spread creep across the entire map
        if self.units(UnitTypeId.QUEEN).amount >= 2:
            self.assignQueenTag()
            await self.doLarvaInjects()

        if self.units(UnitTypeId.QUEEN).amount == 1:
            await self.initial_creep_spread()

    # link up starting base to 2nd/3rd bases with creep
    async def initial_creep_spread(self):

        for queen in self.units(UnitTypeId.QUEEN):
            if queen.energy > 25 and queen.is_idle:
                queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, queen.position.towards(self.game_info.map_center, 8))

    # makes a pixelmap to see creep positions for machine learning..later...maybe
    async def intel(self):
        # print(self.game_info.map_size)
        # flip around. It's y, x when you're dealing with an array.
        game_data = np.zeros((self.game_info.map_size[1], self.game_info.map_size[0], 3), np.uint8)
        # flip horizontally to make our final fix in visual representation:
        flipped = cv2.flip(game_data, 0)
        # enlarge window so a human can see, take out resized and use flipped when doing machine learning
        resized = cv2.resize(flipped, dsize=None, fx=2, fy=2)

        cv2.imshow('Intel', resized)
        cv2.waitKey(1)

        # draws a circle in window showing all tumors / currently not working
        all_creep_tumors: Units = self.structures.of_type(
            {UnitTypeId.CREEPTUMOR, UnitTypeId.CREEPTUMORBURROWED, UnitTypeId.CREEPTUMORQUEEN})
        for tumor in all_creep_tumors:
            tumor_pos = tumor.position
            #print((int(tumor_pos[0]), int(tumor_pos[1])))
            cv2.circle(game_data, (int(tumor_pos[0]), int(tumor_pos[1])), 15, (0, 255, 0), -1)  # BGR
            cv2.imshow('Intel', resized)
            cv2.waitKey(1)

# scouting, need to know what to build before we build it!

# use knowledge from scouting to build defense / offense to counter enemy

# make a basic build in case scouting failed / didn't get enough info


# maps are at E://DiabloTre/StarCraftII/Maps/
run_game(maps.get("AutomatonLE"), [
    Bot(Race.Zerg, Freshbot()),
    Computer(Race.Protoss, Difficulty.Easy)
], realtime=False)
