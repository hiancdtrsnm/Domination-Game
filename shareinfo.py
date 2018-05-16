from newagent import Agent as SuperAgent
from domination.agent import Settings
from domination.core import Observation
import logging
from random import randint, choice
from domination.utilities import find_path, angle_fix, point_dist, line_intersects_grid
from math import atan2
loger = logging.getLogger('myagent')
logging.basicConfig(level=logging.DEBUG)


class Agent(SuperAgent):

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
        self.objectives = {}
        self.goal = None

        self.action = choice([self.share, self.reactive])
        # self.action = self.attacker


    def solve_goal(self, obs):
        if self.goal is None or point_dist(self.goal, obs.loc) < self.settings.tilesize:

            if self.goal is not None:
                self.objectives.pop(self.goal)
                # print('delete {}'.format(self.goal))

            return True
        
        return False

    def share(self):
        obs = self.observation

        # notgets = [cps[0:2] for cps in obs.cps if cps[2] != self.team]
        # for cps in notgets:
        #     if cps not in self.objectives:
        #         self.objectives[cps] = None

        # notgets = [cps[0:2] for cps in obs.cps if cps[2] == self.team]
        # for cps in notgets:
        #     if cps in self.objectives and self.objectives[cps] is not None:
        #         # self.objectives[cps] = None
        #         self.objectives[cps].goal = None
        #         self.objectives.pop(cps)


        ammopacks = [x[0:2] for x in obs.objects if x[2] == "Ammo"]
        for ammo in ammopacks:
            if ammo not in self.objectives:
                self.objectives[ammo] = None

        shoot = self.attacker(obs)
        if shoot: return shoot

        # runaway = self.runanyway(obs)
        # if runaway: 
        #     return runaway

        if self.solve_goal(obs):
            self.goal = None
            goals = [key for key, value in self.objectives.items() if value is None]

            if goals:
                self.goal = choice(goals)
                self.objectives[self.goal] = self
                # print(self.goal)

        if self.goal:
            return self.moveto(obs, self.goal)

        return self.reactive()



    def reactive(self):
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

        return (0, 0, False)
