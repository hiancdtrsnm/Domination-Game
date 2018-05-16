from domination.agent import Agent as BaseAgent
import logging
from random import randint
loger = logging.getLogger('myagent')
logging.basicConfig(level=logging.DEBUG)

class Agent(BaseAgent):
    
    NAME = "Random Agent"

    def action(self):


        obs = self.observation

        # loger.info(self.settings)
        return(randint(0, int(self.settings.max_turn))/4, randint(0, int(self.settings.max_steps)), False)
