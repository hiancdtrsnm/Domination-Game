from domination.agent import Agent as BaseAgent
from domination.agent import Settings
import logging
from random import randint,choice
from domination.utilities import find_path, angle_fix, point_dist, line_intersects_grid
from math import atan2
loger = logging.getLogger('myagent')
logging.basicConfig(level=logging.DEBUG)


class Agent(BaseAgent):

    NAME = "Some Intel"

    def __init__(self, id, team, settings: Settings=None, field_rects=None, field_grid=None, nav_mesh=None, blob=None, **kwargs):
        """ Each agent is initialized at the beginning of each game.
            The first agent (id==0) can use this to set up global variables.
            Note that the properties pertaining to the game field might not be
            given for each game.
        """
        super().__init__(id, team, settings, field_rects, field_grid, nav_mesh, blob, **kwargs)

        self.action = choice([self.pointer, self.attacker])
        # self.action = self.attacker

    def attacker(self):
        obs = self.observation
        if self.goal is not None and point_dist(self.goal, obs.loc) < self.settings.tilesize:
            self.goal = None


        ammopacks = [x for x in obs.objects if x[2] == "Ammo"]
        ammopacks = list(sorted(
            (cps for cps in ammopacks), key=lambda x: point_dist(x, obs.loc)))

    
        if ammopacks:
            self.goal = ammopacks[0][0:2]

        if self.goal:
            path = find_path(obs.loc, self.goal, self.mesh,
                             self.grid, self.settings.tilesize)

        if self.goal and path:
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            speed = (dx**2 + dy**2)**0.5
        else:
            turn = 0
            speed = 0
            speed, turn, shoot = self.pointer()

        shoot = False
        shootgoal = None
        if (obs.ammo > 0 and
            obs.foes and
            point_dist(obs.foes[0][0:2], obs.loc) < self.settings.max_range and
                not line_intersects_grid(obs.loc, obs.foes[0][0:2], self.grid, self.settings.tilesize)):
            shootgoal = obs.foes[0][0:2]
            shoot = True


        if shoot == True and shootgoal:
            path = find_path(obs.loc, shootgoal, self.mesh, self.grid, self.settings.tilesize)
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            if turn > self.settings.max_turn or turn < -self.settings.max_turn:
                shoot = False
            speed = (dx**2 + dy**2)**0.5


        # loger.info(self.settings)
        return(turn, speed, shoot)


    def pointer(self):

        obs = self.observation
        if self.goal is not None and point_dist(self.goal, obs.loc) < self.settings.tilesize:
            self.goal = None
        # print(self.team)

        # self.goal = obs.cps[randint(0, len(obs.cps)-1)][0:2]
        if self.goal is None:
            obj = list(sorted(
                (cps for cps in obs.cps if cps[2] != self.team), key=lambda x: point_dist(x, obs.loc)))
            if obj:
                self.goal = obj[0][0:2]
                self.goal = choice(obj)[0:2]

            else:
                x = map(lambda x: x[0], obs.cps)
                y = map(lambda x: x[1], obs.cps)
                self.goal = obs.loc

        if self.goal:    
            path = find_path(obs.loc, self.goal, self.mesh,
                        self.grid, self.settings.tilesize)

        if self.goal and path:
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            speed = (dx**2 + dy**2)**0.5
        else:
            turn = 0
            speed = 0

        shoot = False
        shootgoal = None
        if (obs.ammo > 0 and
            obs.foes and
            point_dist(obs.foes[0][0:2], obs.loc) < self.settings.max_range and
                not line_intersects_grid(obs.loc, obs.foes[0][0:2], self.grid, self.settings.tilesize)):
            shootgoal = obs.foes[0][0:2]
            shoot = True

        if shoot == True and shootgoal:
            path = find_path(obs.loc, shootgoal, self.mesh,
                             self.grid, self.settings.tilesize)
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            if turn > self.settings.max_turn or turn < -self.settings.max_turn:
                shoot = False
            speed = (dx**2 + dy**2)**0.5

        shoot = False
        shootgoal = None
        if (obs.ammo > 0 and
            obs.foes and
            point_dist(obs.foes[0][0:2], obs.loc) < self.settings.max_range and
                not line_intersects_grid(obs.loc, obs.foes[0][0:2], self.grid, self.settings.tilesize)):
            shootgoal = obs.foes[0][0:2]
            shoot = True

        if shoot == True and shootgoal:
            path = find_path(obs.loc, shootgoal, self.mesh,
                             self.grid, self.settings.tilesize)
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            if turn > self.settings.max_turn or turn < -self.settings.max_turn:
                shoot = False
            speed = (dx**2 + dy**2)**0.5

        # loger.info(self.settings)
        return(turn, speed, False)
