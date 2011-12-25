#!/usr/bin/env python
""" Domination game engine for Reinforcement Learning research.

Contains functions for running multiple games and tournaments.

"""
__author__ = "Thomas van den Berg and Tim Doolan"
__version__ = "1.0"

### IMPORTS ###
# Python
import datetime
import sys
import cPickle as pickle
import zipfile
import math
from optparse import OptionParser

# Local
import core

# Shortcuts
pi = math.pi

### CLASSES ###

class Scenario(object):
    
    SETTINGS = core.Settings()
    FIELD    = core.FieldGenerator().generate()
    EPISODES = 10
    SKIN     = ''
    
    @classmethod
    def observation_function(cls,observation):
        return observation
        
    def setup(self):
        pass
        
    def before_each(self):
        pass
        
    def after_each(self):
        pass
    
    def finalize(self):
        pass
        
    """ You shouldn't have to override any
        of the methods below, but you may.
    """ 
    def __init__(self, red_brain, blue_brain, 
                       red_init={}, blue_init={}):
        self.red_brain = red_brain
        self.blue_brain = blue_brain
        self.red_init = red_init
        self.blue_init = blue_init
        
    def single(self, rendered=False):
        self.before_each()
        game = core.Game(self.red_brain, self.blue_brain,
                    red_init=self.red_init, blue_init=self.blue_init,
                    field=self.FIELD, settings=self.SETTINGS,
                    record=True, verbose=False, rendered=False)
        if rendered:
            game.add_renderer(skin=self.SKIN)
        game.run()
        self.last_game = game
        self.replays.append(game.replay)
        self.stats.append(game.stats)
        self.after_each()
        
    def run(self):
        self.setup()
        self.replays = []
        self.stats = []
        for i in range(self.EPISODES):
            self.single()
            print "Ran %d games."%(i+1)
        now = datetime.datetime.now()
        self.filename = 'dg%s_%s_vs_%s'%(now.strftime("%Y%m%d-%H%M"), self.last_game.red_name, self.last_game.blue_name)
        self.finalize()
        self.write_scores()
        self.save_replays()
        return self # For chaining, if you're into that.
        
    def test(self):
        self.setup()
        self.single(rendered=True)
        self.finalize()
        return self
        
    def write_scores(self):
        statsfile = open(self.filename+'.stats.csv', 'w')
        statsfile.write("# Score, steps\n")
        statsfile.write('\n'.join( "%.2f, %d" % (s.score, s.steps) for s in self.stats ))
        statsfile.close()
        
    def save_replays(self):
        replays = [pickle.dumps(r) for r in self.replays]
        zf = zipfile.ZipFile(self.filename+'.replays.zip','w')
        for i,r in enumerate(replays):
            zf.writestr('replay_%04d.pickle'%i,r)
        zf.close()
        

class VacubotScenario(Scenario):
    SETTINGS = core.Settings(max_speed=20, 
                             max_turn=pi,
                             agent_size=16)
    SKIN     = 'vacubot'
    FIELD    = core.FieldGenerator(width=21, height=15, mirror=False, num_spawns=2).generate()
    
    

### MAIN ###

if __name__ == '__main__':
    VacubotScenario('domination/agent.py','domination/agent.py').run()
