from typing import List
import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.units import Units
from sc2.unit import Unit
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2, Point3
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

        def barracks_points_to_build_addon(sp_position: Point2) -> List[Point2]:
            """ Return all points that need to be checked when trying to build an addon. Returns 4 points. """
            addon_offset: Point2 = Point2((2.5, -0.5))
            addon_position: Point2 = sp_position + addon_offset
            addon_points = [
                (addon_position + Point2((x - 0.5, y - 0.5))).rounded for x in range(0, 2) for y in range(0, 2)
            ]
            return addon_points

        # build techlab on barracks or lift up if no space
        for btl in self.structures(UnitTypeId.BARRACKS).ready.idle:
            if not btl.has_techlab and self.can_afford(UnitTypeId.BARRACKSTECHLAB):
                addon_points = barracks_points_to_build_addon(btl.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    btl.build(UnitTypeId.BARRACKSTECHLAB)
                else:
                    btl(AbilityId.LIFT)

        def barracks_land_positions(sp_position: Point2) -> List[Point2]:
            """ Return all points that need to be checked when trying to land at a location where there is enough space to build an addon. Returns 13 points. """
            land_positions = [(sp_position + Point2((x, y))).rounded for x in range(-1, 2) for y in range(-1, 2)]
            return land_positions + barracks_points_to_build_addon(sp_position)

        # Find a position to land for a flying starport so that it can build an addon
        for sp in self.structures(UnitTypeId.BARRACKSFLYING).idle:
            possible_land_positions_offset = sorted(
                (Point2((x, y)) for x in range(-10, 10) for y in range(-10, 10)),
                key=lambda point: point.x ** 2 + point.y ** 2,
            )
            offset_point: Point2 = Point2((-0.5, -0.5))
            possible_land_positions = (sp.position.rounded + offset_point + p for p in possible_land_positions_offset)
            for target_land_position in possible_land_positions:
                land_and_addon_points: List[Point2] = barracks_land_positions(target_land_position)
                if all(
                    self.in_map_bounds(land_pos) and self.in_placement_grid(land_pos) and self.in_pathing_grid(land_pos)
                    for land_pos in land_and_addon_points
                ):
                    sp(AbilityId.LAND, target_land_position)
                    break

        # Show where it is flying to and show grid
        unit: Unit
        for sp in self.structures(UnitTypeId.BARRACKSFLYING).filter(lambda unit: not unit.is_idle):
            if isinstance(sp.order_target, Point2):
                p: Point3 = Point3((*sp.order_target, self.get_terrain_z_height(sp.order_target)))
                self.client.debug_box2_out(p, color=Point3((255, 0, 0)))

        # Stimpack research, super important
        if self.already_pending_upgrade(UpgradeId.STIMPACK) == 0 and self.can_afford(UpgradeId.STIMPACK):
            bar_techlab_ready: Units = self.structures(UnitTypeId.BARRACKSTECHLAB).ready
            if bar_techlab_ready:
                self.research(UpgradeId.STIMPACK)
                self.stim_started = True

    async def expand(self):
        if self.units(UnitTypeId.COMMANDCENTER).amount < 2 and self.can_afford(UnitTypeId.COMMANDCENTER):
            await self.expand_now()


run_game(maps.get("AutomatonLE"), [
    Bot(Race.Terran, TerrantestBot()),
    Computer(Race.Protoss, Difficulty.Easy)
], realtime=True)
