import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.units import Units
from sc2.unit import Unit
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.player import Bot, Computer


class TerrantestBot(sc2.BotAI):
    def __init__(self):
        self.stim_started = False

    def select_target(self):
        target = self.enemy_structures
        if target.exists:
            return target.random.position

        target = self.enemy_units
        if target.exists:
            return target.random.position

        if min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5:
            return self.enemy_start_locations[0].position

        else:
            return self.mineral_field.random.position

    async def on_step(self, iteration):
        await self.distribute_workers()
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER) | self.townhalls(UnitTypeId.ORBITALCOMMAND)
        if not ccs:
            target: Point2 = self.enemy_structures.random_or(self.enemy_start_locations[0]).position
            for unit in self.workers | self.units(UnitTypeId.MARINE):
                unit.attack(target)
            return
        else:
            cc: Unit = ccs.first

        if iteration % 50 == 0 and self.units(UnitTypeId.MARINE).amount > 12:
            target = self.select_target()
            forces = self.units(UnitTypeId.MARINE) | self.units(UnitTypeId.MEDIVAC)
            if (iteration // 50) % 10 == 0:
                for unit in forces:
                    unit.attack(target)
            else:
                for unit in forces.idle:
                    unit.attack(target)

        if self.can_afford(UnitTypeId.SCV) and self.workers.amount < 30 and cc.is_idle:
            cc.train(UnitTypeId.SCV)

        for bar in self.structures(UnitTypeId.BARRACKS).ready.idle:
            if self.can_afford(UnitTypeId.MARINE):
                bar.train(UnitTypeId.MARINE)

        for sp in self.structures(UnitTypeId.STARPORT).ready.idle:
            if self.can_afford(UnitTypeId.MEDIVAC) and self.units.of_type(UnitTypeId.MEDIVAC).amount < 6:
                sp.train(UnitTypeId.MEDIVAC)

        if self.supply_left < 3:
            if self.can_afford(UnitTypeId.SUPPLYDEPOT) and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
                await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 8))

        if self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            if (
                self.can_afford(UnitTypeId.BARRACKS)
                and not self.already_pending(UnitTypeId.BARRACKS)
                and self.structures(UnitTypeId.BARRACKS).amount < 4
            ):
                await self.build(UnitTypeId.BARRACKS, near=cc.position.towards(self.game_info.map_center, 8))

        if self.structures(UnitTypeId.BARRACKS).exists and self.structures(UnitTypeId.REFINERY).amount < 2:
            if self.can_afford(UnitTypeId.REFINERY):
                vgs: Units = self.vespene_geyser.closer_than(20.0, cc)
                for vg in vgs:
                    if self.structures(UnitTypeId.REFINERY).closer_than(1.0, vg).exists:
                        break

                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break
                    worker.build(UnitTypeId.REFINERY, vg)
                    break

        if self.structures(UnitTypeId.BARRACKS).ready.exists:
            f = self.structures(UnitTypeId.FACTORY)
            if not f.exists:
                if self.can_afford(UnitTypeId.FACTORY):
                    await self.build(UnitTypeId.FACTORY, near=cc.position.towards(self.game_info.map_center, 8))
            elif f.ready.exists and self.structures(UnitTypeId.STARPORT).amount < 1:
                if self.can_afford(UnitTypeId.STARPORT):
                    await self.build(UnitTypeId.STARPORT,
                                     near=cc.position.towards(self.game_info.map_center, 15).random_on_distance(8))

        for a in self.structures(UnitTypeId.REFINERY):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    w.random.gather(a)

        for scv in self.units(UnitTypeId.SCV).idle:
            scv.gather(self.mineral_field.closest_to(cc))

        if self.structures(UnitTypeId.BARRACKS).ready:
            for bar in self.units(UnitTypeId.BARRACKS).ready:
                if bar.add_on_tag == 0 and not self.structures(UnitTypeId.BARRACKSTECHLAB).exists:
                    await bar.build(UnitTypeId.BARRACKSTECHLAB)

        # Trying to get Stimpack Research but failing, gets assertion error
        if self.vespene >= 100 and not self.stim_started:
            btl = self.units(UnitTypeId.BARRACKSTECHLAB).ready.idle
            if btl.exists and self.minerals >= 100:
                if not self.already_pending_upgrade(UpgradeId.BARRACKSTECHLABRESEARCH_STIMPACK):
                    btl(AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK)
                    self.stim_started = True

    async def expand(self):
        if self.units(UnitTypeId.COMMANDCENTER).amount < 2 and self.can_afford(UnitTypeId.COMMANDCENTER):
            await self.expand_now()


run_game(maps.get("AutomatonLE"), [
    Bot(Race.Terran, TerrantestBot()),
    Computer(Race.Protoss, Difficulty.Easy)
], realtime=False)
