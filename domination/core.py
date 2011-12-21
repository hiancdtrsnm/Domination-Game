#!/usr/bin/env python
""" Domination game engine for Reinforcement Learning research.

This is the game engine module that can simulate games, without rendering them.
Refer to the readme for usage instructions.

In short, the most easy way to get started (after importing) is to
give two paths to the run_games() function.

>>> run.games('agent.py','agent.py')
"""
__author__ = "Thomas van den Berg and Tim Doolan"
__version__ = "1.0"

### IMPORTS ###
# Python
import random
import sys
import re
import math
import time
import datetime
import itertools
import copy
import traceback
import bisect
from pprint import pprint

# Local
from utilities import *
from libs import *

# Shortcuts
sqrt = math.sqrt
inf  = float('inf')
pi   = math.pi
sin  = math.sin
cos  = math.cos
rand = random.random

### CONSTANTS###
TEAM_RED     = 0
TEAM_BLUE    = 1
TEAM_NEUTRAL = 2

CAPTURE_MODE_NEUTRAL  = 0
CAPTURE_MODE_FIRST    = 1
CAPTURE_MODE_MAJORITY = 2

ENDGAME_NONE   = 0 #0b00
ENDGAME_SCORE  = 1 #0b01
ENDGAME_CRUMBS = 2 #0b10

AGENT_GLOBALS = globals().copy()

### CLASSES ###

class Settings(object):
    def __init__(self, max_steps=500,
                       max_score=1000,
                       max_turn=pi/3,
                       max_speed=40,
                       max_range=60,
                       max_see=100,
                       field_known=True,
                       ammo_rate=20,
                       ammo_amount=3,
                       spawn_time=10,
                       field_width=47,
                       field_height=32,
                       tilesize=16,
                       think_time=0.010,
                       capture_mode=CAPTURE_MODE_NEUTRAL,
                       end_condition=ENDGAME_SCORE,
                       num_agents=5):
        self.max_steps     = max_steps     # How long the game will last at most
        self.max_score     = max_score     # If either team scores this much, the game is finished
        self.max_speed     = max_speed     # Number of game units each tank can drive in its turn
        self.max_turn      = max_turn      # The maximum angle that a tank can rotate in a turn
        self.max_range     = max_range     # The shooting range of tanks in game units
        self.max_see       = max_see       # How far tanks can see (Manhattan distance)
        self.field_known   = field_known   # Whether the agents have knowledge of the field at game start
        self.ammo_rate     = ammo_rate     # How long it takes for ammo to reappear
        self.ammo_amount   = ammo_amount   # How many bullets there are in each ammo pack
        self.spawn_time    = spawn_time    # Time that it takes for tanks to respawn
        self.field_width   = field_width   # How wide the field is in tiles, should be odd
        self.field_height  = field_height  # Height of the field in tiles
        self.tilesize      = tilesize      # How big a single tile is (game units), change at own risk
        self.think_time    = think_time    # How long the tanks have to do their computations (in seconds)
        self.capture_mode  = capture_mode  # Behavior of controlpoints when multiple agents are on them
        self.end_condition = end_condition # FLAGS for end condition of game. (So you can set multiple using "OR")
        self.num_agents    = num_agents    # Number of agents per team
        # Validate
        if max_score % 2 != 0:
            raise Exception("Max score (%d) has to be even."%max_score)
        if field_width % 2 == 0:
            raise Exception("Field width (%d) must be odd."%field_width)
        
    def __repr__(self):
        default = Settings()
        args = ('%s=%r'%(v,getattr(self,v)) for v in vars(self) if getattr(self,v) != getattr(default,v))
        args = ','.join(args)
        return 'Settings(%s)'%args
                
class GameStats(object):
    def __init__(self):
        self.score_red = 0
        self.score_blue = 0
        self.score = 0.0
        self.steps = 0
        self.crumbs_red = 0
        self.crumbs_blue = 0
        self.ammo_red = 0
        self.ammo_blue = 0
    
    def __str__(self):
        return "%d steps. Score: %d-%d."%(self.steps,self.score_red,self.score_blue) 
    
class Game(object):
    
    """ The main game class. Contains game data and methods for
        simulation.
    """
    
    SIMULATION_SUBSTEPS = 10
    SIMULATION_MAXITER  = 10
    
    STATE_NEW       = 0
    STATE_READY     = 1
    STATE_RUNNING   = 2
    STATE_INTERRUPT = 3
    STATE_ENDED     = 4
        
    def __init__(self, red_brain='agent.py',
                       blue_brain='agent.py',
                       red_brain_string=None,
                       blue_brain_string=None,
                       settings=Settings(),
                       field=None,
                       red_init={},
                       blue_init={},
                       record=False,
                       replay=None,
                       rendered=True, 
                       verbose=True):
        """ Constructor for Game class 
            
            :param red_brain:         File that the red brain class resides in.
            :param blue_brain:        File that the blue brain class resides in.
            :param red_brain_string:  If passed, a string containing the blue brain class. 
                                        Overrides red_brain argument.
            :param blue_brain_string: Same as red_brain_string.
            :param settings:          Instance of the settings class.
            :param field:             An instance of Field to play this game on. 
            :param red_init:          A dictionary of keyword arguments passed to the red
                                        agent constructor.
            :param blue_init:         Like red_init.
            :param record:            Store all actions in a game replay.
            :param replay:            Pass a game replay to play it.
            :param rendered:          Enable/disable the renderer.
            :param verbose:           Print game log to output.
        """

        self.record = record
        self.replay = replay
        self.verbose = verbose
        if self.record and self.replay is not None:
            raise Exception("Cannot record and play replay at the same time.")
        # Set up a new game
        if replay is None:
            self.settings = settings
            self.red_brain = red_brain
            self.blue_brain = blue_brain
            self.red_init = red_init
            self.blue_init = blue_init
            # Generate new game field if a generator was passed
            if field is None:
                self.field = FieldGenerator().generate()
            else:
                self.field = field
            # Read agent brains (from string or file)
            g = AGENT_GLOBALS.copy()
            if red_brain_string is not None:
                exec(red_brain_string, g)
            else:
                execfile(red_brain, g)
            self.red_brain_class = g['Agent']
            self.red_name = self.agent_name(self.red_brain_class)
            # Blue brain
            if blue_brain_string is not None:
                exec(blue_brain_string, g)
            else:
                execfile(blue_brain, g)
            self.blue_brain_class = g['Agent']
            self.blue_name = self.agent_name(self.blue_brain_class)
        # Load up a replay
        else:
            self.log('[Game]: Playing replay.')
            if replay.version != __version__:
                raise Exception("Replay is for older game version.")
            self.settings = replay.settings
            self.field = replay.field

        # Variables for performance timing
        self.sim_time = 0.0 
        # Create the renderer if needed
        if rendered:
            self.add_renderer()
        else:
            self.renderer = None
        
        self.interrupted = False
        self.clicked = None
        self.keys = []
        self.state = Game.STATE_NEW
        
    def agent_name(self, agent_class):
        """ Retrieves the name of an agent
            This is defined by a static property NAME in the agent's class.
        """
        unsafe_chars = r'[^a-z0-9\-]+'
        if hasattr(agent_class, "NAME"):
            n = re.sub(unsafe_chars, '-', agent_class.NAME)
            return n[:16]
        else:
            return "noname"
        
    def add_renderer(self, **kwargs):
        import renderer
        globals()['renderer'] = renderer
        self.renderer = renderer.Renderer(self.field, **kwargs)
        
    def setup(self):
        """ Sets up the game. Can be called on a game that has
            already finished once, to play the game again
            on the same map. Note that the game is deterministic,
            so if there is no random behavior in the agents, the
            outcome of each game will be identical.
        """
        # Initialize new replay
        if self.record:
            self.replay = ReplayData(self)
        # Load field objects
        (allobjects, cps, reds, blues) = self.field.get_objects()
        # Game logic variables
        self.score_red  = self.settings.max_score / 2
        self.score_blue = self.settings.max_score / 2
        self.step       = 0
        # Simulation variables
        self.objects         = []
        self.broadphase_mov  = []
        self.broadphase_stat = []
        # Performance tracking
        self.stats = GameStats()
        self.think_time_red         = 0.0
        self.think_time_blue        = 0.0
        self.think_time_red_total   = 0.0
        self.think_time_blue_total  = 0.0
        self.update_time_total      = 0.0
        self.sim_time_total         = 0.0
        self.agent_raised_exception = False
        # Game objects
        self.tanks         = []
        self.controlpoints = []
        for o in allobjects:
            self.add_object(o)
        self.controlpoints = cps
        # Initialize tanks
        if self.record or self.replay is None:
            # Initialize new tanks with brains
            for i,s in enumerate(reds):
                if self.settings.field_known:
                    brain = self.red_brain_class(i,TEAM_RED,settings=copy.copy(self.settings), field_rects=self.field.wallrects,
                                             field_grid=self.field.walls, nav_mesh=self.field.mesh, **self.red_init)
                else:
                    brain = self.red_brain_class(i,TEAM_RED,settings=copy.copy(self.settings), **self.red_init)
                t = Tank(s.x+2, s.y+2, s.angle, i, team=TEAM_RED, brain=brain, spawn=s, record=self.record)
                self.tanks.append(t)
                self.add_object(t)
            for i,s in enumerate(blues):
                if self.settings.field_known:
                    brain = self.blue_brain_class(i,TEAM_BLUE,settings=copy.copy(self.settings), field_rects=self.field.wallrects,
                                             field_grid=self.field.walls, nav_mesh=self.field.mesh, **self.blue_init)
                else:
                    brain = self.red_brain_class(i,TEAM_RED,settings=copy.copy(self.settings), **self.red_init)
                t = Tank(s.x+2, s.y+2, s.angle, i, team=TEAM_BLUE, brain=brain, spawn=s, record=self.record)
                self.tanks.append(t)
                self.add_object(t)
        else:
            # Initialize tanks to play replays
            for i,(s,a) in enumerate(zip(reds,self.replay.actions_red)):
                t = Tank(self, s.x+2, s.y+2, s.angle, i, team=TEAM_RED, spawn=s, actions=a)
                self.tanks.append(t)
                self.add_object(t)
            for i,(s,a) in enumerate(zip(blues,self.replay.actions_blue)):
                t = Tank(self, s.x+2, s.y+2, s.angle, i, team=TEAM_BLUE, spawn=s, actions=a)
                self.tanks.append(t)
                self.add_object(t)
        self.tanks_red = [tank for tank in self.tanks if tank.team == TEAM_RED]
        self.tanks_blue = [tank for tank in self.tanks if tank.team == TEAM_BLUE]
        self.state = Game.STATE_READY
        self.interrupted = False
        
    def run(self):
        """ Start and loop the game. """
        if self.state != Game.STATE_READY:
            self.setup()
        res      = Game.SIMULATION_SUBSTEPS
        render   = self.renderer is not None
        settings = self.settings
        ## MAIN GAME LOOP
        self.state = Game.STATE_RUNNING
        try:
            for s in xrange(settings.max_steps):
                self.step = s+1
                ## UPDATE & CHECK VICTORY
                p = time.clock()
                for o in self.objects:
                    o.update()
                for t in self.tanks:
                    t.send_observation()
                for t in self.tanks:
                    t.get_action()
                # Compute shooting
                for tank in self.tanks:
                    if tank.shoots:
                        tcx, tcy = tank._x + tank.width/2, tank._y + tank.height/2
                        target = (cos(tank.angle) * settings.max_range + tcx, 
                                  sin(tank.angle) * settings.max_range + tcy)
                        hits   = self.raycast((tcx, tcy), target, exclude=tank)
                        tank._hitx, tank._hity = target
                        if hits:
                            t, (px,py), who = hits[0]
                            tank._hitx, tank._hity = px, py
                            if isinstance(who, Tank):
                                who.respawn_in = self.settings.spawn_time
                
                # Record times
                self.update_time_total += time.clock() - p
                sum_red = sum(tank.time_thought for tank in self.tanks_red)
                sum_blue = sum(tank.time_thought for tank in self.tanks_blue)
                self.think_time_red_total += sum_red
                self.think_time_blue_total += sum_blue
                if self.tanks_red:
                    self.think_time_red = sum_red / len(self.tanks_red)
                if self.tanks_blue:
                    self.think_time_blue = sum_blue / len(self.tanks_blue)
                # Score ending condition
                if ((self.settings.end_condition & ENDGAME_SCORE) and 
                    (self.score_red == 0 or self.score_blue == 0)):
                    break
                # No crumbs left ending condition
                if ((self.settings.end_condition & ENDGAME_CRUMBS) and
                    not any(True for o in allobjects if isinstance(o, Crumb))):
                    break
                ## RESET SOME STUFF
                if render:
                    self.clicked = None
                    self.keys = []
                ## SIMULATE AND RENDER
                for o in self.objects:
                    if o.movable:
                        o._dx = (o.x - o._x) / res
                        o._dy = (o.y - o._y) / res
                        if render:
                            o._da = (o.angle - o._a) / renderer.ROTATION_FRAMES
                # Render rotation/shooting
                if render:
                    for _ in xrange(renderer.ROTATION_FRAMES):
                        for o in self.objects:
                            o._a += o._da
                        self.renderer.render(self)
                    for f in xrange(renderer.SHOOTING_FRAMES):
                        self.renderer.render(self, shooting_frame = f)
                
                # Reset tanks that got shot
                for tank in self.tanks:
                    if tank.respawn_in == self.settings.spawn_time:
                        tank.ammo = 0
                        tank.x = tank._x = tank.spawn.x + 2
                        tank.y = tank._y = tank.spawn.y + 2
                        tank._dx = tank._dy = 0
                        tank.angle = tank._a = tank.spawn.angle                        
                
                # Simulate/Render movement
                self.sim_time = 0.0
                for step in xrange(res):
                    p = time.clock()
                    self.substep()
                    self.sim_time += time.clock() - p
                    if render:
                        self.renderer.render(self)
                self.sim_time_total += self.sim_time
                for o in self.objects:
                    if o.movable:
                        o.x = o._x
                        o.y = o._y
                        o._a = o.angle = angle_fix(o.angle)
        except GameInterrupt:
            self.state = Game.STATE_INTERRUPT
        except KeyboardInterrupt:
            self.state = Game.STATE_INTERRUPT
        self.end(interrupted=(self.state==Game.STATE_INTERRUPT))
        return self # For chaining, if you're into that.
    
    def end(self, interrupted=False):
        """ End the game, writes scores to a file and tells all the agents
            that the game is over so that they can write any remaining info.
        """
        if interrupted:
            print "Game was interrupted."
            self.interrupted = True
        self.state = Game.STATE_ENDED
        self.stats.score_red = self.score_red
        self.stats.score_blue = self.score_blue
        self.stats.score = self.score_red / float(self.score_red + self.score_blue)
        self.stats.steps = self.step
        self.log(str(self.stats))
        if self.record:
            self.replay.settings = copy.copy(self.settings)
            self.replay.settings.max_steps = self.step
            self.replay.field    = self.field
            self.replay.actions_red = [tank.actions for tank in self.tanks_red]
            self.replay.actions_blue = [tank.actions for tank in self.tanks_blue]
        # Finalize tanks brains.
        if self.record or self.replay is None:
            for tank in self.tanks:
                tank.brain.finalize(interrupted)
    
    def substep(self):
        """ Performs a single physics substep. All objects are moved by
            their respective _dx and _dy amounts, collisions are computed,
            and all objects are repeatedly separated until no large collisions
            occur anymore. 
        """
        for o in self.broadphase_mov:
            o._x += o._dx
            o._y += o._dy
            o._moved = True # if (o._dx != 0 or o._dy != 0) else False
        something_collided = True
        iteration = Game.SIMULATION_MAXITER
        pairs = set([])
        while something_collided and iteration > 0:
            self.broadphase_mov.sort(key=lambda o:o._x)
            collisions = []
            k = 0
            for i, o1 in enumerate(self.broadphase_mov):
                for o2 in self.broadphase_mov[i+1:]:
                    # If the object didn't move, no need to check.
                    if o2._moved or o1._moved: 
                        # Break if the next object's _x is already outside
                        # this object's bounds. (The essential bit)
                        if o2._x >= o1._x + o1.width:
                            break
                        # Otherwise check if the y's intersect too
                        if o2._y < (o1._y + o1.height) and o1._y < (o2._y + o2.height):
                            sep = self.compute_separation(o1,o2)
                            if sep is not None:
                                if o1.solid and o2.solid:
                                    collisions.append(sep)
                                pairs.add(((o1,o2) if id(o1) < id(o2) else (o2, o1)))
                if o1._moved:
                    sf = True
                    for o2 in self.broadphase_stat[k:]:
                        # Maintain marker index for static broadphase
                        if o2._x + o2.width <= o1._x:
                            if sf:
                                k += 1
                            continue
                        elif sf:
                            sf = False
                        # Break if the next object's _x is already outside
                        # this object's bounds. (The essential bit)
                        if o2._x >= o1._x + o1.width:
                            break
                        # Otherwise check if the y's intersect too
                        if o2._y < (o1._y + o1.height) and o1._y < (o2._y + o2.height):
                            sep = self.compute_separation(o1,o2)
                            if sep is not None:
                                if o1.solid and o2.solid:
                                    collisions.append(sep)
                                pairs.add((o1,o2) if (id(o1) < id(o2)) else (o2, o1))
                    o1._moved = False
            something_collided = len(collisions) > 0
            # Sort the collisions on their first property, the penetration distance.
            collisions.sort(reverse=True)
            for (p, o1, o2, px, py) in collisions:
                if p < 1: 
                    break
                if not o1._moved and not o2._moved:
                    if o1.movable:
                        if o2.movable:
                            dx = px/2
                            dy = py/2
                            o1._x += dx
                            o1._y += dy
                            o2._x -= dx
                            o2._y -= dy
                            o1._moved = True
                            o2._moved = True
                        else:
                            o1._x += px
                            o1._y += py
                            o1._moved = True
                    else:
                        o2._x -= px
                        o2._y -= py
                        o2._moved = True
            iteration -= 1
        for (o1,o2) in pairs:
            o1.collide(o2)
            o2.collide(o1)
        
    def add_object(self,o):
        """ Add an object to the game and collision list. """
        o.game = self
        self.objects.append(o)
        if o.physical:
            if o.movable:
                self.broadphase_mov.append(o)
                self.broadphase_mov.sort(key=lambda o:o._x)
            else:
                self.broadphase_stat.append(o)
                self.broadphase_stat.sort(key=lambda o:o._x)
        o.added_to_game(self)
        
    def rem_object(self,o):
        """ Removes an object from the game and collision lists. """
        self.objects.remove(o)
        if o.physical:
            if o.movable:
                self.broadphase_mov.remove(o)
            else:
                self.broadphase_stat.remove(o)
        # Check if we need to remove this object from a parent
        if hasattr(o, 'parent'):
            o.parent.remove_child(o)
                
    def get_objects_in_bounds(self, xmin, xmax, ymin, ymax, solid_only=True):
        """ Return a list of all objects whose bounding boxes
            intersect the given bounds.
        """
        for o in self.broadphase_mov:
            if o._x > xmax:
                break
            if (not solid_only or o.solid) and o._x + o.width > xmin:
                if ymin < (o._y + o.height) and o._y < ymax:
                    yield o
        for o in self.broadphase_stat:
            if o._x > xmax:
                break
            if (not solid_only or o.solid) and o._x + o.width > xmin:
                if ymin < (o._y + o.height) and o._y < ymax:
                    yield o
    
    def compute_separation(self, object1, object2):
        """ Compute object separation/penetration
            Returns a tuple or None.
            The tuple consists of the penetration distance, 
            both objects, and the required movement of _object1_ 
            to separate.
        """
        # Find out what kind of collision we're dealing with
        # The circle proxy is either a real circle, or a rect's corner 
        # that another circle collides with.
        sep_as_circles   = False
        objects_switched = False
        if ((object1.shape == GameObject.SHAPE_CIRC) and
            (object2.shape == GameObject.SHAPE_CIRC)):
            circleproxy = (object1._x + object1.width, object1._y + object1.height, object1.width/2)
            sep_as_cicles = True
        elif ((object1.shape == GameObject.SHAPE_RECT) and
            (object2.shape == GameObject.SHAPE_RECT)):
            sep_as_circles = False
        else:
            if (object1.shape == GameObject.SHAPE_CIRC):
                switched = True
                (object1, object2) = (object2, object1)
            cx   = object2._x + object2.width/2
            cy   = object2._y + object2.height/2
            ra   = object2.width/2
            l, t = object1._x, object1._y
            r, b = l + object1.width, t + object1.height
            if cx < l:
                if cy < t:
                    circleproxy    = (l,t,0.0)
                    sep_as_circles = True
                elif cy > b:
                    circleproxy    = (l,b,0.0)
                    sep_as_circles = True
            elif cx > r:
                if cy < t:
                    circleproxy = (r,t,0.0)
                    sep_as_circles = True
                elif cy > b: 
                    circleproxy = (r,b,0.0)
                    sep_as_circles = True
        # Separate Circle/Circle
        if sep_as_circles:
            (cx,cy,ra) = circleproxy
            md = ra + object2.width / 2 # Minimum distance
            dx = (cx + ra) - (object2._x + object2.width/2)
            dy = (cy + ra) - (object2._y + object2.height/2)
            ds = dx*dx + dy*dy          # Actual distance squared
            if ds == 0:
                p,px,py = 0.0, 0.0, 0.0
            elif ds < md*md:
                d  = sqrt(ds)   # Actual Distance
                p  = md - d     # Penetration amount
                f  = p/d
                px = f * dx
                py = f * dy
            else:
                return None
        # Separate Rect/Rect
        else:
            o1l, o1t = object1._x, object1._y
            o1r, o1b = o1l + object1.width, o1t + object1.height
            o2l, o2t = object2._x, object2._y
            o2r, o2b = o2l + object2.width, o2t + object2.height
            p,px,py  = inf, 0, 0
            # Try to find the side with the smallest separation distance
            pt = o1r - o2l # Left side penetration
            if 0 < pt:
                p, px, py  = pt, -pt, 0.0
            else:
                return None
            pt  = o1b - o2t # Top penetration
            if 0 < pt:
                if pt < p:
                    p, px, py = pt, 0.0, -pt
            else: 
                return None
            pt = o2r - o1l # Right side penetration
            if 0 < pt:
                if pt < p:
                    p, px, py = pt, pt, 0.0
            else:
                return None
            pt = o2b - o1t # Bottom penetration (really...)
            if 0 < pt:
                if pt < p:
                    p, px, py  = pt, 0.0, pt
            else:
                return None
        if objects_switched:
            object1, object2 = object2, object1
            px, py = -px, -py
        return (p, object1, object2, px, py)
        
    def raycast(self, p0, p1, exclude=None):
        """ Shoots a ray from p0 to p1 and determines
            which objects are hit and at what time
            in the parametric line equation p0 + t*(p1-p0)
        """
        p0x, p0y = p0
        p1x, p1y = p1
        xmin, xmax = (p0x, p1x) if p0x < p1x else (p1x, p0x)
        ymin, ymax = (p0y, p1y) if p0y < p1y else (p1y, p0y)
        
        # List collided pairs
        in_box = self.get_objects_in_bounds(xmin,xmax,ymin,ymax)
        # Determine actual hits
        hits = []
        for o in in_box:
            if o != exclude:
                if o.shape == GameObject.SHAPE_RECT:
                    isect = line_intersects_rect(p0,p1,(o._x,o._y,o.width,o.height))
                    if isect:
                        # Append the t0 (intersection time) and object
                        hits.append((isect[0][0],isect[0][1],o))
                elif o.shape == GameObject.SHAPE_CIRC:
                    r = o.width/2
                    isect = line_intersects_circ(p0,p1,(o._x+r,o._y+r),r)
                    if isect:
                        # Append the t0 (intersection time), position and object
                        hits.append((isect[0][0],isect[0][1],o))
        hits.sort()
        return hits
    
    def click(self, pos):
        """ Tells the game that the right-mouse button was clicked
            somewhere on the field.
        """
        self.clicked = pos
    
    def keypress(self, key):
        """ Tells the game that some key on the keyboard was pressed.
        """
        self.keys.append(key)
        
    def select_tanks(self, rect, team=0):
        """ Function that can be called by the renderer to set
            selected=True on tanks in the given rectangle. Handy
            for manually selecting and controlling tanks.
        """
        x,y,w,h = rect
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        for t in self.tanks:
            if (t._x < x+w and 
                t._y < y+h and
                t._x + t.width > x and
                t._y + t.height > y) and t.team == team:
                t.selected = True
            else:
                t.selected = False 
    
    def log(self, message):
        """Logs the given message, and prints it if
        verbose is set to True
        """
        if self.verbose:
            print message
            
    def __str__(self):
        args = ','.join(['%r'%self.red_name,
                         '%r'%self.blue_name,
                         'settings=%r'%self.settings])
        if self.red_init != {}:
            args += ',red_init=%r'%self.red_init
        if self.blue_init != {}:
            args += ',blue_init=%r'%self.blue_init
        return 'Game(%s)'%args


class Field(object):
    """ Class representing a playing field.
        
        You can use to_file, which dumps an ASCII representation of the
        field to a file, or you can pickle the entire Field object.
        Any way to create a Field is fine, the included FieldGenerator
        does a pretty good job!
    """
    def __init__(self, width, height, tilesize):
        # Settings variables
        self.width            = width
        self.height           = height
        self.tilesize         = tilesize
        
        # Instantiated variables
        self.walls         = [] # The tilemap of the walls
        self.spawns_red    = [] # Separate lists of red/blue spawns
        self.spawns_blue   = []
        self.controlpoints = []
        self.other_objects = []
        
    @classmethod
    def from_string(cls, s):
        """ Returns a new Field from given ASCII representation. """
        field = cls()
        lines = [l.split() for l in s.strip().split('\n')]
        field.height,field.width = len(lines),len(lines[0])
        for i,line in enumerate(lines):
            row = []
            for j, tile in enumerate(line):
                row.append(1 if tile=='w' else 0)
                if tile.lower() == 'c':
                    field.controlpoints.append((j,i))
                elif tile.lower() == 'r':
                    field.spawns_red.append((j,i,0))
                elif tile.lower() == 'b':
                    field.spawns_blue.append((j,i,-pi))
                elif tile.lower() == 'a':
                    field.ammo.append((j,i))
            field.walls.append(row)
        field.instantiated = True
        return field
    
    def __str__(self):
        s = []
        for row in self.walls:
            s.append([])
            for tile in row:
                s[-1].append('w' if tile else '_')
        for (j,i) in self.controlpoints:
            s[i][j] = 'C'
        for (j,i) in self.ammo:
            s[i][j] = 'A'
        for (j,i,d) in self.spawns_red:
            s[i][j] = 'R'
        for (j,i,d) in self.spawns_blue:
            s[i][j] = 'B'
        return '\n'.join([' '.join(row) for row in s])
    
    def to_file(self, filename):
        o = str(self)
        f = open(filename,'w')
        f.write(o)
    
    def get_objects(self):
        """ Generates all GameObjects and returns them. """
        ts = self.tilesize
        ## Walls
        walls = [Wall(x=w[0],y=w[1],width=w[2],height=w[3]) for w in self.wallrects]
        ## Controlpoints
        ofs = (ts-ControlPoint.SIZE)/2
        cps = [ControlPoint(x=x*ts+ofs, y=y*ts+ofs) for (x,y) in self.controlpoints]
        ## Spawns
        ofs = (ts-TankSpawn.SIZE)/2
        redspawns = [TankSpawn(x=x*ts+ofs,y=y*ts+ofs,angle=r,team=TEAM_RED) for (x,y,r) in self.spawns_red]
        bluespawns = [TankSpawn(x=x*ts+ofs,y=y*ts+ofs,angle=r,team=TEAM_BLUE) for (x,y,r) in self.spawns_blue]
        ## Other Objects
        other = []
        for (x, y, class_string) in self.other_objects:
            cls = globals()[class_string]
            ofs = (ts-cls.SIZE)/2.0
            other.append(cls(x=x*ts+ofs, y=y*ts+ofs))
        # Return assorted tuples
        allobjects = walls + cps + redspawns + bluespawns + other
        return (allobjects, cps, redspawns, bluespawns)
        
class FieldGenerator(object):
    """ Generates field objects from random distribution """
    
    def __init__(self, width=39, height=24, tilesize=16,
                       num_spawns=5, num_points=3, num_ammo=6, 
                       wall_fill=0.4, wall_len=(4,4), wall_width=4, 
                       wall_orientation=0.5, wall_gridsize=4):
        self.width            = width
        self.height           = height
        self.tilesize         = tilesize
        self.num_spawns       = num_spawns
        self.num_points       = num_points
        self.num_ammo         = num_ammo
        self.wall_fill        = wall_fill
        self.wall_len         = wall_len
        self.wall_width       = wall_width
        self.wall_orientation = wall_orientation
        self.wall_gridsize    = wall_gridsize
    
    @classmethod
    def reflect_tilemap(cls, tilemap, newsize, axis_vertical=True):
        """ Reflects a tilemap (2D-list) along an arbitrary horizontal
            or vertical axis. Odd-sized arrays will work too.
        """
        # Transpose
        if axis_vertical:
            tilemap = zip(*tilemap)
        # Build new tilemap
        newtiles = []
        for i in xrange(newsize):
            newtiles.append(tilemap[i][:] if i < newsize//2 else tilemap[newsize-1-i][:])
        # Transpose back
        if axis_vertical:
            return [list(l) for l in zip(*newtiles)]
    
    @classmethod
    def clear_walls_under_objects(cls, field):
        for (x, y, r) in field.spawns_red + field.spawns_blue:
            field.walls[y][x] = 0
            field.walls[int(y+sin(r)+0.5)][int(x+cos(r)+0.5)] = 0
        for (x, y) in field.controlpoints:
            for i in xrange(y-1,y+2):
                for j in xrange(x-1,x+2):
                    field.walls[i][j] = 0
        for (x, y, _) in field.other_objects:
            field.walls[y][x] = 0
            
    def generate(self):
        """ Generates a new field using the parameters for random 
            distribution set in the constructor. 
        """
        # Create a new field
        field = Field(width=self.width, height=self.height, tilesize=self.tilesize)
        ## 1) Place objects on map
        self.place_objects(field)
        ## 2) Generate tilemap
        self.create_wall_map(field)
        ## 3) Clear walls under objects
        self.clear_walls_under_objects(field)
        ## 4) Make rects from walls and generate mesh
        wallrects = []
        ts = self.tilesize
        for i,row in enumerate(field.walls):
            for j,tile in enumerate(row):
                if tile:
                    wallrects.append((j*ts,i*ts,ts,ts))
        field.wallrects = rects_merge(wallrects)
        all_objects = field.get_objects()[0]
        add_points = [(o.cx, o.cy) for o in all_objects if (isinstance(o,Ammo) or isinstance(o,ControlPoint))]
        field.mesh = make_nav_mesh(field.wallrects, (0,0,self.width*self.tilesize,self.height*self.tilesize),
                                    simplify=0.3,additional_points=add_points)
        return field
    
    def place_objects(self, field):
        """ (Randomly) places important objects on the map. """
        spawn  = (2,1)
        cpleft = ((self.width-1)/4, (self.height-1)-3)
        cpmid  = (self.width/2, random.randint(3,self.height/2+1))
        ## Generate mirrored object locations
        # Spawn regions
        i,j = spawn[0], spawn[1]
        while len(field.spawns_red) < self.num_spawns:
            field.spawns_red.append((i, j, 0))
            field.spawns_blue.append((self.width-1-i, j, -pi))
            i += 1
            if i >= spawn[0] + 2:
                j += 1
                i = spawn[0]
        # Controlpoints
        field.controlpoints.append((cpleft[0], cpleft[1]))
        field.controlpoints.append((cpmid[0], cpmid[1]))
        field.controlpoints.append((self.width-1-cpleft[0], cpleft[1]))
        # Ammo
        for _ in xrange(self.num_ammo//2):
            x,y = (random.randint(3,self.width//2-1),random.randint(5,self.height-2))
            field.other_objects.append((x, y, "AmmoFountain"))
            field.other_objects.append((self.width-1-x, y, "AmmoFountain"))
        
    def create_wall_map(self, field):     
        # Find free routes
        spawn = field.spawns_red[0][:2]
        reachable_points = field.controlpoints + field.other_objects + field.spawns_red + field.spawns_blue
        reachable_points = [r[:2] for r in reachable_points] # Grab only (x,y)
        # Create outer walls
        halfwidth = int(0.5+ self.width/2.0)
        t         = [1] * halfwidth
        m         = [1] + [0] * (halfwidth-1)
        b         = [1] * halfwidth
        tilemap   = [t]
        for i in xrange(self.height-2):
            tilemap.append(m[:])
        tilemap.append(b)
        min_filled = 0.5*self.height*self.width*self.wall_fill
        if len(self.wall_len) == 2:
            min_len, max_len = self.wall_len
        else:
            min_len, max_len = self.wall_len, self.wall_len
        failed = 0
        while sum(sum(row) for row in tilemap) < min_filled and failed < 100:
            new = copy.deepcopy(tilemap)
            # Create horizontal section
            if rand() < self.wall_orientation:
                sec_width = random.randint(min_len,max_len)
                sec_height = self.wall_width
            # Create vertical section
            else:
                sec_width = self.wall_width
                sec_height = random.randint(min_len,max_len)
            x,y = (random.randint(1,halfwidth-sec_width), random.randint(1,self.height-sec_height-1))
            x = (x // self.wall_gridsize) * self.wall_gridsize
            y = (y // self.wall_gridsize) * self.wall_gridsize
            for i in xrange(y, y + sec_height):
                for j in xrange(x, x + sec_width):
                    new[i][j] = 1
            reachability = reachable(self.reflect_tilemap(new, self.width), field.spawns_red[0][:2])
            if all(reachability[y][x] for (x,y) in reachable_points):
                tilemap = new
            else:
                failed += 1
        field.walls = self.reflect_tilemap(tilemap, self.width)


class GameObject(object):
    """ Generic game object """
    
    SHAPE_RECT = 0
    SHAPE_CIRC = 1
    
    SIZE       = 12
    
    def __init__(self, x=0.0, y=0.0, width=12, height=12, angle=0, shape=0, 
                       solid=True, movable=True, physical=True, graphic='default'):
        # Game variables
        self.x        = float(x)
        self.y        = float(y)
        self.width    = float(width)
        self.height   = float(height)
        self.angle    = float(angle)
        self.shape    = shape
        self.solid    = solid
        self.movable  = movable
        self.physical = physical
        self.graphic  = graphic   # Graphic used by the renderer.
        if not movable:
            self.cx = int(x + self.SIZE/2)
            self.cy = int(y + self.SIZE/2)
        # Internal vars, used by the collision detection
        self._x     = self.x
        self._y     = self.y
        self._a     = self.angle
        self._dx    = 0.0
        self._dy    = 0.0
        self._da    = 0.0
        self._moved = False
        
    def added_to_game(self, game):
        """ Tells the object that it has been added to the game,
            that includes having its ".game" attribute set.
        """
        pass
        
    def update(self):
        """ Tells this object to update its game state.
            Only called once per game-step.
        """
        pass
        
    def collide(self, other):
        """ Informs the object that it has collided with another.
            Is called once per simulation substep.
        """
        pass
    
    def __hash__(self):
        return id(self)
        
        
## Gameobject Subclasses

class Tank(GameObject):
    SIZE = 16
    
    def __init__(self,
                 x=0, y=0, angle=0, id=0, team=TEAM_RED,
                 brain=None, spawn=None, actions=None, record=False):
        super(Tank, self).__init__(x=x, y=y, angle=angle, width=self.SIZE, height=self.SIZE,
                    shape=GameObject.SHAPE_CIRC, solid=True, movable=True)
        if team == TEAM_RED:
            self.graphic = 'tank_red'
        else:
            self.graphic = 'tank_blue'
        self.brain       = brain
        self.id          = id
        self.team        = team
        self.ammo        = 0
        self.selected    = False
        self.shoots      = False
        self.respawn_in  = -1
        self.spawn       = spawn
        # A list of actions, either for recording or playing back.
        self.actions = actions if actions is not None else []
        self.record = record
        self.time_thought = 0.0
        # Additional hidden vars
        self._hitx = 0.0
        self._hity = 0.0
        self.grid_x = 0
        self.grid_y = 0
        
    def added_to_game(self, game):
        # Initialize observation
        self.observation = Observation()
        gridrng = (self.game.settings.max_see/2+1)//game.field.tilesize
        self.observation.walls = [[0 for _ in xrange(gridrng*2+1)] for _ in xrange(gridrng*2+1)]
        
    def update(self):
        # Check alive status
        if self.respawn_in == 0:
            self.respawn_in = -1
        elif self.respawn_in > 0:
            self.respawn_in -= 1
            
    def send_observation(self):
        rng = self.game.settings.max_see
        obs = self.observation
        siz = self.width / 2.0
        obs.step       = self.game.step
        obs.loc        = mx, my = (int(self.x+siz), int(self.y+siz))
        obs.angle      = self.angle
        obs.ammo       = self.ammo
        obs.friends    = []
        obs.foes       = []
        obs.objects    = []
        obs.respawn_in = self.respawn_in
        obs.score      = (self.game.score_red, self.game.score_blue)
        obs.selected   = self.selected
        obs.clicked    = self.game.clicked
        obs.keys       = self.game.keys
        close = self.game.get_objects_in_bounds(self.x - rng, self.x + self.width + rng,
                    self.y - rng, self.y + self.height + rng, solid_only=False)
        
        for o in close:
            if isinstance(o, Tank):
                if o.team == self.team:
                    if o != self:
                        obs.friends.append((int(o._x+siz), int(o._y+siz)))
                else:
                    obs.foes.append((int(o._x+siz), int(o._y+siz), o._a))
            elif isinstance(o, Ammo):
                obs.objects.append((o.cx, o.cy, "Ammo"))
            elif isinstance(o, Crumb):
                obs.objects.append((o.cx, o.cy, "Crumb"))
        obs.cps = [(cp.cx,cp.cy,cp.team) for cp in self.game.controlpoints]
        # Observe walls
        f = self.game.field
        xj, yi = mx//f.tilesize, my//f.tilesize
        # Only regenerate grid if we moved to another cell.
        if xj != self.grid_x or yi != self.grid_y:
            gridrng = (rng/2+1)//f.tilesize
            w,h = f.width, f.height
            for oi,i in enumerate(xrange(yi-gridrng, yi+gridrng+1)):
                for oj,j in enumerate(xrange(xj-gridrng, xj+gridrng+1)):
                    if (i >= 0 and j >= 0 and i < h and j < w and
                        f.walls[i][j] == 0):
                        obs.walls[oi][oj] = 0
                    else:
                        obs.walls[oi][oj] = 1
            self.grid_x = xj
            self.grid_y = yi
        if self.brain is not None:
            last_clock = time.clock()
            try:
                self.brain.observe(obs)
            except Exception, e:
                self.game.agent_raised_exception = True
                print "[Game]: Agent %s-%d raised exception:"%('RED' if self.team == 0 else 'BLU',self.id)
                print '-'*60
                traceback.print_exc(file=sys.stdout)
                print '-'*60            
            self.time_thought = time.clock() - last_clock
        
    def get_action(self):
        ## Ask brain for action (or replay)
        if not self.record and self.actions:
            (turn, speed, shoot) = self.actions.pop(0)
        else:
            last_clock = time.clock()
            try:
                (turn,speed,shoot) = self.brain.action()
            except Exception, e:
                self.game.agent_raised_exception = True
                print "[Game]: Agent %s-%d raised exception:"%('RED' if self.team == 0 else 'BLU',self.id)
                print '-'*60
                traceback.print_exc(file=sys.stdout)
                print '-'*60
                (turn,speed,shoot) = (0,0,False)
            self.time_thought += time.clock() - last_clock
            # Ignore action (NO-OP) if agent thought too long.
            if self.time_thought > self.game.settings.think_time:
                (turn, speed, shoot) = (0,0,False)
                self.game.log('[Game]: Agent %s-%d timed out (%.3fs).'%('RED'if self.team==0 else 'BLU',self.id,self.time_thought))
            if self.record:
                self.actions.append((turn,speed,shoot))
            if self.game.renderer is not None and self.game.renderer.active_team == self.team:
                self.brain.debug(self.game.renderer.agent_debug)
        self.shoots = False
        if self.respawn_in == -1:
            max_turn = self.game.settings.max_turn
            speed = min(self.game.settings.max_speed, speed)
            turn = max(-max_turn, min(max_turn, angle_fix(turn)))
            self.angle += turn
            self.x += math.cos(self.angle)*speed
            self.y += math.sin(self.angle)*speed
            # Process shooting
            if shoot and self.ammo > 0:
                self.shoots = True
                self.ammo -= 1
        
    def collide(self, other):
        if isinstance(other, Tank):
            self.observation.collided = True
        elif isinstance(other, Wall):
            self.observation.collided = True
            

class Wall(GameObject):
    def __init__(self, **kwargs):
        kwargs['graphic'] = None
        kwargs['movable'] = False
        kwargs['solid'] = True
        super(Wall, self).__init__(**kwargs)

class ControlPoint(GameObject):
    SIZE = 24
    def __init__(self,x,y):
        super(ControlPoint, self).__init__(x=x, y=y, width=ControlPoint.SIZE, height=ControlPoint.SIZE, shape=GameObject.SHAPE_CIRC, 
                                           solid=False, movable=False, graphic='cp_neutral')
        self.team = TEAM_NEUTRAL
        self.collided = [0, 0, 0]
    
    def update(self):
        self.collided = [0, 0, 0]
        if self.team == TEAM_RED and self.game.score_red < self.game.settings.max_score:
            self.game.score_red += 1
            self.game.score_blue -= 1
        elif self.team == TEAM_BLUE and self.game.score_blue < self.game.settings.max_score:
            self.game.score_blue += 1
            self.game.score_red -= 1
    
    def collide(self, other):
        if isinstance(other, Tank):
            # Neutral
            if self.game.settings.capture_mode == 0:
                if self.collided[self.team] > 0 and self.team != other.team:
                    self.team = TEAM_NEUTRAL
                else:
                    self.team = other.team
                    self.collided[self.team] += 1
            # Closest to center
            elif self.game.settings.capture_mode == 1:
                if self.collided[self.team] > 0:
                    pass
                else:
                    self.team = other.team
                    self.collided[self.team] += 1
            # Majority 
            elif self.game.settings.capture_mode == 2:
                self.collided[other.team] += 1
                if self.team != other.team and self.collided[other.team] == self.collided[self.team]:
                    self.team = TEAM_NEUTRAL
                elif self.collided[other.team] > self.collided[self.team]:
                    self.team = other.team
            
            if self.team == TEAM_RED:
                self.graphic = 'cp_red'
            elif self.team == TEAM_BLUE:
                self.graphic = 'cp_blue'
            else:
                self.graphic = 'cp_neutral'
                

        
class Ammo(GameObject):
    """ Represents an ammo pack.
    """
    SIZE = 16
    def __init__(self,x,y):
        super(Ammo, self).__init__(x=x, y=y, width=Ammo.SIZE, height=Ammo.SIZE, 
                                   shape=GameObject.SHAPE_CIRC, solid=False, 
                                   movable=False, graphic='ammo_full')
        self.pickedup = False
    
    def collide(self, other):
        if not self.pickedup and isinstance(other, Tank):
            if other.team == TEAM_RED:
                self.game.stats.ammo_red += 1
            elif other.team == TEAM_BLUE:
                self.game.stats.ammo_blue += 1
            other.ammo += self.game.settings.ammo_amount
            self.game.rem_object(self)
            self.pickedup = True

class Crumb(GameObject):
    """ Represents a crumb, something that can be picked
        up, with no other purpose than being registered
        as picked up.
    """
    SIZE = 4
    def __init__(self, x, y):
        super(Crumb, self).__init__(x=x, y=y, width=Crumb.SIZE, height=Crumb.SIZE, 
                                        shape=GameObject.SHAPE_RECT, solid=False, 
                                        movable=False, graphic='crumb')
        self.pickedup = False                                
    
    def collide(self, other):
        if not self.pickedup and isinstance(other, Tank):
            if other.team == TEAM_RED:
                self.game.stats.crumbs_red += 1
            elif other.team == TEAM_BLUE:
                self.game.stats.crumbs_blue += 1
            self.game.rem_object(self)
            self.pickedup = True

class Fountain(GameObject):
    """ A non-physical object that spawns other objects at 
        regular intervals, or when there are too few
        of its 'child' objects on the map.
    """
    MIN_CHILDREN = 1
    DELAY        = 10
    CHILD_CLASS  = Ammo
    SIZE         = 16
    GRAPHIC      = None
    
    def SPREAD(self, x, y):
        return (x,y)
    
    def __init__(self, x, y):
        super(Fountain, self).__init__(x=x, y=y, width=self.SIZE, height=self.SIZE, 
                                   shape=GameObject.SHAPE_RECT, solid=False, 
                                   movable=False, physical=False, graphic=self.GRAPHIC)
        self.countdown = -1
        self.children = []
        self.initialized = False
        
    def added_to_game(self, game):
        while len(self.children) < self.MIN_CHILDREN:
            self.spawn_one()
        
    def update(self):
        # Charge slowly
        if self.countdown > -1:
            self.countdown -= 1         
        if self.countdown == -1 and len(self.children) < self.MIN_CHILDREN:
            self.countdown = self.DELAY
        if self.countdown == 0:
            self.spawn_one()
            
    def remove_child(self, child):
        self.children.remove(child)
            
    def spawn_one(self, attempts = 10):
        while attempts:
            (x,y) = self.SPREAD(self.x + self.width/2.0, self.y + self.height/2.0)
            f = self.game.field
            # Check if we're not spawning our object into a wall.
            (j,i) = int(x//f.tilesize), int(y//f.tilesize)
            if 0 <= i < f.height and 0 <= j < f.width and not f.walls[i][j]:
                c = self.CHILD_CLASS(x - self.CHILD_CLASS.SIZE/2.0, y - self.CHILD_CLASS.SIZE/2.0)
                c.parent = self
                self.children.append(c)
                self.game.add_object(c)
                return
            attempts -= 1
            
class AmmoFountain(Fountain):
    MIN_CHILDREN = 1
    CHILD_CLASS  = Ammo
    SIZE         = 16
    GRAPHIC      = 'ammo_empty'
            
    def added_to_game(self, game):
        self.DELAY = self.game.settings.ammo_rate
        super(AmmoFountain, self).added_to_game(game)
                
class CrumbFountain(Fountain):
    MIN_CHILDREN = 100
    DELAY        = -1
    CHILD_CLASS  = Crumb
    SIZE         = 50
    
    def SPREAD(self, x, y):
        return x + random.gauss(0, self.SIZE), y + random.gauss(0, self.SIZE)

class TankSpawn(GameObject):
    SIZE = 16
    def __init__(self,x=0, y=0, angle=0, team=TEAM_RED, brain=None):
        super(TankSpawn, self).__init__(x=x, y=y, angle=angle, width=TankSpawn.SIZE, height=TankSpawn.SIZE, 
                                        shape=GameObject.SHAPE_RECT, solid=False, movable=False, physical=False)
        self.team = team
        self.graphic = 'spawn_red' if self.team == TEAM_RED else 'spawn_blue'

class Observation(object):
    def __init__(self):
        self.step       = 0     # Current timestep
        self.loc        = (0,0) # Agent's location (x,y)
        self.angle      = 0     # Current angle in radians
        self.walls      = []    # Visible walls around the agent: a 2D binary array
        self.friends    = []    # All/Visible friends: a list of (x,y,angle)-tuples
        self.foes       = []    # Visible foes: a list of (x,y,angle)-tuples
        self.cps        = []    # Controlpoints: a list of (x,y,TEAM_RED/TEAM_BLUE)-tuples
        self.objects    = []    # Visible objects: a list of (x,y,type)-tuples
        self.ammo       = 0     # Ammo count
        self.score      = (0,0) # Current game score
        self.collided   = False # Whether the agent has collided in the previous turn
        self.respawn_in = -1    # How many timesteps left before this agent can move again.
        # The following properties are only set when
        # the renderer is enabled:
        self.selected = False   # Indicates if the agent is selected in the UI
        self.clicked = None     # Indicates the position of a right-button click, if there was one
        self.keys = []          # A list of all keys pressed in the previous turn
        
## Replay Classes

class ReplayData(object):
    def __init__(self, game):
        self.settings = game.settings
        self.version = __version__
        self.actions_red  = [] # List of lists of red agents' actions
        self.actions_blue = [] # List of lists of blue agents' actions

    def play(self):
        """ Convenience method for setting up a game to play this replay. 
        """
        g = Game(replay=self,rendered=True)
        g.run()
        return g