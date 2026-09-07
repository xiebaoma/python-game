"""Logic-level regression tests for the tower-defense mechanics."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from cyber_guard.entities import Enemy, Tower
from cyber_guard.game import CyberGuardGame


class EnemyTests(unittest.TestCase):
    def test_enemy_follows_route(self):
        enemy = Enemy("packet", 1)
        start = enemy.pos.copy()
        enemy.update(0.5)
        self.assertGreater(enemy.pos.distance_to(start), 1)
        self.assertFalse(enemy.escaped)

    def test_slow_reduces_movement(self):
        normal = Enemy("packet", 1)
        slowed = Enemy("packet", 1)
        slowed.apply_slow(0.5, 2.0)
        normal.update(1.0)
        slowed.update(1.0)
        self.assertGreater(normal.distance_travelled, slowed.distance_travelled)


class TowerTests(unittest.TestCase):
    def test_target_priority_prefers_more_advanced_enemy(self):
        tower = Tower("scanner", (100, 180))
        first = Enemy("packet", 1)
        second = Enemy("packet", 1)
        first.pos = pygame.math.Vector2(80, 112)
        first.path_index = 0
        first.distance_travelled = 120
        second.pos = pygame.math.Vector2(165, 180)
        second.path_index = 1
        second.distance_travelled = 10
        self.assertIs(tower.choose_target([first, second]), second)

    def test_upgrade_increases_damage_and_range(self):
        tower = Tower("firewall", (300, 180))
        base_damage = tower.damage
        base_range = tower.attack_range
        tower.upgrade()
        self.assertGreater(tower.damage, base_damage)
        self.assertGreater(tower.attack_range, base_range)


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = CyberGuardGame(headless=True)
        self.game.start_game()

    def tearDown(self):
        pygame.quit()

    def test_build_validation_rejects_path_and_accepts_open_ground(self):
        self.assertFalse(self.game.is_valid_build((165, 112)))
        self.assertTrue(self.game.is_valid_build((288, 192)))

    def test_placing_tower_spends_resources(self):
        before = self.game.money
        built = self.game.place_tower("scanner", (288, 192))
        self.assertTrue(built)
        self.assertEqual(before - 90, self.game.money)

    def test_wave_populates_spawn_queue(self):
        self.assertTrue(self.game.start_wave())
        self.assertTrue(self.game.wave_active)
        self.game.update(0.1)
        self.assertGreater(len(self.game.enemies) + len(self.game.spawn_queue), 0)

    def test_emergency_scan_consumes_energy_and_deals_damage(self):
        enemy = Enemy("bot", 1)
        self.game.enemies.append(enemy)
        self.game.energy = 100
        hp_before = enemy.hp
        self.assertTrue(self.game.activate_scan())
        self.assertEqual(self.game.energy, 40)
        self.assertLess(enemy.hp, hp_before)


if __name__ == "__main__":
    unittest.main()
