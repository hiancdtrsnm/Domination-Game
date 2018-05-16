from domination.agent import Agent as BaseAgent
from domination.agent import Settings
from domination.core import Observation
import logging
from random import randint, choice
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
        super().__init__(id, team, settings, field_rects,
                         field_grid, nav_mesh, blob, **kwargs)

        self.defobj = None

        # self.action = self.attacker

    def action(self):
        obs = self.observation

        scorer = self.soccorer(obs)
        ammo = self.ammopicker(obs)
        shoot = self.attacker(obs)
        runaway = self.runanyway(obs)
        defense = self.defense(obs)

        if shoot:
            return shoot

        if runaway:
            return runaway

        if ammo:
            return ammo

        if scorer:
            return scorer

        if defense:
            return defense

        return (0,0,False)

    def soccorer(self, obs: Observation):


        # goal = obs.cps[randint(0, len(obs.cps)-1)][0:2]
        obj = list(sorted(
            (cps for cps in obs.cps if cps[2] != self.team), key=lambda x: point_dist(x, obs.loc)))
        if obj:
            goal = obj[0][0:2]
            goal = choice(obj)[0:2]

            x = map(lambda x: x[0], obs.cps)
            y = map(lambda x: x[1], obs.cps)

            path = find_path(obs.loc, goal, self.mesh,
                                self.grid, self.settings.tilesize)

            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            speed = (dx**2 + dy**2)**0.5

            return (turn, speed, False)
        return tuple()



    def ammopicker(self, obs: Observation):

        ammopacks = [x for x in obs.objects if x[2] == "Ammo"]
        ammopacks = list(sorted(
            (cps for cps in ammopacks), key=lambda x: point_dist(x, obs.loc)))

        if ammopacks:

            goal = ammopacks[0][0:2]
            path = find_path(obs.loc, goal, self.mesh,
                             self.grid, self.settings.tilesize)
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            speed = (dx**2 + dy**2)**0.5
            return (turn, speed, False)

        
        turn = 0
        speed = 0
        return tuple()


    def attacker(self, obs: Observation):

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

        if not shoot:
            return tuple()

        return (turn, speed, shoot)

    def runanyway(self, obs: Observation):

        shootgoal = None
        if (obs.ammo > 0 and
            obs.foes and
            point_dist(obs.foes[0][0:2], obs.loc) < self.settings.max_range and
                not line_intersects_grid(obs.loc, obs.foes[0][0:2], self.grid, self.settings.tilesize)):
            shootgoal = obs.foes[0][0:2]

        if shootgoal:
            path = find_path(obs.loc, shootgoal, self.mesh,
                             self.grid, self.settings.tilesize)
            dx = path[0][0] - obs.loc[0]
            dy = path[0][1] - obs.loc[1]
            turn = angle_fix(atan2(dy, dx) - obs.angle)
            if turn > self.settings.max_turn and turn > 0:
                turn = max(turn, self.settings.max_turn)
            elif turn < -self.settings.max_turn and turn < 0:
                turn = min(turn, -self.settings.max_turn)
            speed = (dx**2 + dy**2)**0.5
            return (turn, speed, False)

        return tuple()


    def moveto(self, obs, point):

        obj = point
        goal = point
        path = find_path(obs.loc, goal, self.mesh,
                            self.grid, self.settings.tilesize)

        dx = path[0][0] - obs.loc[0]
        dy = path[0][1] - obs.loc[1]
        turn = angle_fix(atan2(dy, dx) - obs.angle)
        speed = (dx**2 + dy**2)**0.5

        return (turn, speed, False)

    def defense(self, obs):
        if not self.defobj:
            self.defobj = choice([cps[0:2] for cps in obs.cps])


        return self.moveto(obs, self.defobj)

