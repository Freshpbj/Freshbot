import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.effect_id import EffectId
from sc2.player import Bot, Computer


class TerrantestBot(sc2.BotAI):
    def __init__(self):
        self.stim_started = False

    def select_target(self):
        target = self.known_enemy_structures
        if target.exists:
            return target.random.position

        target = self.known_enemy_units
        if target.exists:
            return target.random.position

        if min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5:
            return self.enemy_start_locations[0].position

        return self.state.mineral_field.random.position

    async def on_step(self, iteration):
        await self.distribute_workers()
        await self.expand()
        cc = (self.units(COMMANDCENTER) | self.units(ORBITALCOMMAND))
        if not cc.exists:
            target = self.known_enemy_structures.random_or(self.enemy_start_locations[0]).position
            for unit in self.workers | self.units(MARINE):
                await self.do(unit.attack(target))
            return
        else:
            cc = cc.first


        if iteration % 50 == 0 and self.units(MARINE).amount > 12:
            target = self.select_target()
            forces = self.units(MARINE) | self.units(MEDIVAC)
            if (iteration//50) % 10 == 0:
                for unit in forces:
                    await self.do(unit.attack(target))
            else:
                for unit in forces.idle:
                    await self.do(unit.attack(target))

        if self.can_afford(SCV) and self.workers.amount < 30 and cc.noqueue:
            await self.do(cc.train(SCV))

        if self.units(BARRACKS).exists and self.can_afford(MARINE):
            for bar in self.units(BARRACKS):
                if bar.has_add_on and bar.noqueue:
                    if not self.can_afford(MARINE):
                        break
                    await self.do(bar.train(MARINE))

        if self.units(STARPORT).exists and self.can_afford(MEDIVAC) and self.units(MEDIVAC).amount < 6:
            for sp in self.units(STARPORT):
                if sp.noqueue:
                    if not self.can_afford(MEDIVAC):
                        break
                    await self.do(sp.train(MEDIVAC))

        elif self.supply_left < 3:
            if self.can_afford(SUPPLYDEPOT):
                await self.build(SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 8))

        if self.units(SUPPLYDEPOT).exists:
            if not self.units(BARRACKS).exists:
                if self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
                    await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 8).random_on_distance(4))
            elif len(self.units(BARRACKS)) < 4:
                if self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
                    await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 8).random_on_distance(4))

            elif self.units(BARRACKS).exists and self.units(REFINERY).amount < 2:
                if self.can_afford(REFINERY):
                    vgs = self.state.vespene_geyser.closer_than(20.0, cc)
                    for vg in vgs:
                        if self.units(REFINERY).closer_than(1.0, vg).exists:
                            break

                        worker = self.select_build_worker(vg.position)
                        if worker is None:
                            break

                        await self.do(worker.build(REFINERY, vg))
                        break

            if self.units(BARRACKS).ready.exists:
                f = self.units(FACTORY)
                if not f.exists:
                    if self.can_afford(FACTORY):
                        await self.build(FACTORY, near=cc.position.towards(self.game_info.map_center, 8))
                elif f.ready.exists and self.units(STARPORT).amount < 1:
                    if self.can_afford(STARPORT):
                        await self.build(STARPORT, near=cc.position.towards(self.game_info.map_center, 15).random_on_distance(8))

        for a in self.units(REFINERY):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    await self.do(w.random.gather(a))

        for scv in self.units(SCV).idle:
            await self.do(scv.gather(self.state.mineral_field.closest_to(cc)))

        for bar in self.units(BARRACKS).ready:
            if bar.add_on_tag == 0 and not self.units(BARRACKSTECHLAB).exists:
                await self.do(bar.build(BARRACKSTECHLAB))

# Trying to get Stimpack Research but failing, gets assertion error
        if self.vespene >= 100 and not self.stim_started:
            btl = self.units(BARRACKSTECHLAB).ready
            abilities = await self.get_available_abilities(btl)
            if btl.exists and self.minerals >= 100:
                if AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK in abilities:
                    if not self.already_pending_upgrade(BARRACKSTECHLABRESEARCH_STIMPACK):
                        await self.do(btl(AbilityID.BARRACKSTECHLABRESEARCH_STIMPACK))
                        self.stim_started = True


    async def expand(self):
        if self.units(COMMANDCENTER).amount < 2 and self.can_afford(COMMANDCENTER):
            await self.expand_now()

run_game(maps.get("AutomatonLE"), [
        Bot(Race.Terran, TerrantestBot()),
        Computer(Race.Protoss, Difficulty.Easy)
    ], realtime = False)