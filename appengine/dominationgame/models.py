### Imports ###

# Python Imports
import os
import re
import hashlib
import logging
import base64 as b64
from datetime import datetime, date, time, timedelta

# AppEngine Imports
from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.api.app_identity import get_application_id, get_default_version_hostname

# Django Imports
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify

# Library Imports
from domination import core as domcore
import trueskill


### Constants ###
APP_URL = "http://localhost:8082"
MAX_ACTIVE_BRAINS = 3

### Exceptions ###

### Properties ###

class TimeDeltaProperty(db.Property):
    """ Timedelta in seconds, stored as integer """
    def get_value_for_datastore(self, model_instance):
        td = super(TimeDeltaProperty, self).get_value_for_datastore(model_instance)
        if td is not None:
            return (td.seconds + td.days * 86400)
        return None
    
    def make_value_from_datastore(self, value):
        if value is not None:
            return timedelta(seconds=value)
            
class DictProperty(db.StringProperty):
    """ Quick 'n dirty way to store a dictionary in de datastore"""

    def get_value_for_datastore(self, model_instance):
        d = super(DictProperty, self).get_value_for_datastore(model_instance)
        if d is not None:
            return repr(d)
        return None
    
    def make_value_from_datastore(self, value):
        if value is not None:
            return eval(value)

    def validate(self, value):
        if value is not None and type(value) != dict:
            raise db.BadValueError("%r must be a dict."%value)

class SlugProperty(db.StringProperty):
    """A (rough) App Engine equivalent to Django's SlugField."""
    
    def __init__(self, auto_calculate, **kwargs):
        """Initialize a slug with the property to base it on.
        """
        super(SlugProperty, self).__init__(**kwargs)
        self.auto_calculate = auto_calculate

    def get_value_for_datastore(self, model_instance):
        """Convert slug into format to go into the datastore."""
        value = self.auto_calculate.__get__(model_instance, None)
        return unicode(slugify(value))

    def validate(self, value):
        """Validate the slug meets formatting restrictions."""
        # Django does [^\w\s-] to '', strips, lowers, then [-\s] to '-'.
        if value and (value.lower() != value or ' ' in value):
            raise db.BadValueError("%r must be lowercase and have no spaces" % value)
        return super(SlugProperty, self).validate(value)

### Models ###

class Group(db.Model):
    name = db.StringProperty(required=True)
    slug = SlugProperty(name)
    added = db.DateTimeProperty(auto_now_add=True)
    active = db.BooleanProperty(default=True)
    # Group settings
    gamesettings = DictProperty(default={})
    release_delay = TimeDeltaProperty(default=timedelta(days=10))
    
    def __str__(self):
        return self.name
    
    def url(self):
        if self.slug is None:
            self.slug = slugify(self.name)
        return reverse("dominationgame.views.group", args=[self.slug])
        
    def ladder(self):
        recent = datetime.now() - timedelta(days=7)
        q = self.brain_set.filter('last_played > ',recent)
        return sorted(q, key=lambda b: b.conservative, reverse=True)
        
    def recent_games(self):
        return self.game_set.order('-added').fetch(10)
    
class Team(db.Model):
    group       = db.ReferenceProperty(Group, required=True)
    name        = db.StringProperty(required=True)
    number      = db.IntegerProperty(default=1)
    hashed_code = db.StringProperty(required=True)
    added       = db.DateTimeProperty(auto_now_add=True)
    emails      = db.StringListProperty()
    # Brains
    brain_ver   = db.IntegerProperty(default=0)
    actives = db.ListProperty(db.Key)
    
    @classmethod
    def create(cls, group, **kwargs):
        kwargs['hashed_code'] = b64.urlsafe_b64encode(os.urandom(32))
        kwargs['number'] = Team.all().count() + 1
        kwargs['parent'] = group
        return cls(group=group, **kwargs)
        
    @classmethod
    def get_by_secret_code(cls, secret_code):
        hashed_code = b64.urlsafe_b64encode(hashlib.sha224(secret_code).digest())
        return cls.all().filter('hashed_code =', hashed_code).get()
        
    def activate(self, brains):
        for brain in self.brain_set:
            brain.active = False
        for i,brain in enumerate(brains):
            brain.active = True
        self.actives = [b.key() for b in brains]
        db.put(self.brain_set.fetch(10000))
    
    def send_invites(self):
        secret_code = b64.urlsafe_b64encode(os.urandom(32))
        self.hashed_code = b64.urlsafe_b64encode(hashlib.sha224(secret_code).digest())
        url = APP_URL + reverse("dominationgame.views.connect_account") + '?c=' + secret_code
        mailbody = """
                L.S.
                
                This is an invitation to join a team for the Domination game.
                You've been invited to join %s.
                Use the following link to confirm:
                
                %s
                
                Regards,
                
                Your TA
                """%(str(self), url)
        logging.info(mailbody)
        for email in self.emails:
            mail.send_mail(sender="noreply@%s.appspotmail.com"%get_application_id(),
                           to=email,
                           subject="Invitation to join a team for %s"%(self.group.name),
                           body=mailbody)
        self.put()
        
        
    def __str__(self):
        return "Team %d: %s"%(self.number, self.name)

    def url(self):
        return reverse("dominationgame.views.team", args=[self.group.slug, self.key().id()])
        
    def members(self):
        """ Returns a list of members """
        return Account.all().filter('teams', self.key())
        
    def activebrains(self):
        """ Returns dereferenced active brains """
        return Brain.get(self.actives)
        
    def activebrainkeyids(self):
        """ Returns key.id's for active brains """
        return [str(k.id()) for k in self.actives]
        
    def allbrains(self):
        """ Returns this team's brains, but ordered. """
        return self.brain_set.order('added')
        

class Account(db.Model):
    added = db.DateTimeProperty(auto_now_add=True)
    nickname = db.StringProperty()
    teams = db.ListProperty(db.Key)
    
    current_team = None
    
class Brain(db.Model):
    # Performance stats
    score        = db.FloatProperty(default=100.0)
    uncertainty  = db.FloatProperty(default=30.0)
    conservative = db.FloatProperty(default=100.0)
    active       = db.BooleanProperty(default=False)
    games_played = db.IntegerProperty(default=1)
    num_errors   = db.IntegerProperty(default=0)
    # Identity
    group   = db.ReferenceProperty(Group, required=True)
    team    = db.ReferenceProperty(Team, required=True)
    name    = db.StringProperty(default='unnamed')
    version = db.IntegerProperty(default=1)
    # Timestamps
    added       = db.DateTimeProperty(auto_now_add=True)
    modified    = db.DateTimeProperty(auto_now=True)
    last_played = db.DateTimeProperty()
    # Source code
    source       = db.TextProperty(required=True)
    
    def __str__(self):
        return mark_safe("%s v%d"%(self.name, self.version))
    
    @classmethod
    def create(cls, team, source, **kwargs):
        kwargs['version'] = team.brain_ver + 1
        kwargs['group'] = team.group
        # Try to extract a name
        namerx = r'NAME *= *[\'\"]([a-zA-Z0-9\-\_ ]+)[\'\"]'
        match = re.search(r'NAME *= *[\'\"]([a-zA-Z0-9\-\_ ]+)[\'\"]', source)
        if match:
            kwargs['name'] = match.groups(1)[0]
        # Create entity and put
        brain = cls(team=team, source=source, parent=team.group, **kwargs)
        team.brain_ver += 1
        team.put()
        brain.put()
        return brain
        
    def played_game(self, (score, uncertainty), error=False):
        self.score = score
        self.uncertainty = uncertainty
        self.conservative = score - uncertainty
        self.last_played = datetime.now()
        self.games_played += 1
        if error:
            self.num_errors += 1
        
    def url(self):
        return reverse("dominationgame.views.brain", args=[self.group.slug, self.key().id()])
                
    def release_date(self):
        return self.added + self.group.release_delay
        
    def released(self):
        return self.release_date() < datetime.now()
        
        
class Game(db.Model):
    added = db.DateTimeProperty(auto_now_add=True)
    group = db.ReferenceProperty(Group, required=True)
    red = db.ReferenceProperty(Brain, collection_name="red_set")
    blue = db.ReferenceProperty(Brain, collection_name="blue_set")
    score_red = db.IntegerProperty()
    score_blue = db.IntegerProperty()
    error_red = db.BooleanProperty(default=False)
    error_blue = db.BooleanProperty(default=False) 
    stats = db.TextProperty()
    log = db.TextProperty()
    winner = db.StringProperty(choices=["red","blue","draw"])

    
    @classmethod
    def play(cls, red_key, blue_key, ranked=True):
        """ Play and store a single game. """
        # Dereference the keys
        red = Brain.get(red_key)
        blue = Brain.get(blue_key)
        # Run a game
        logging.info("Running game: %s %s vs %s %s"%(red.team, red, blue.team, blue))
        dg = domcore.Game(red_brain_string=red.source,
                          blue_brain_string=blue.source,
                          verbose=False, rendered=False)
        dg.run()
        logging.info("Game done.")
        # Extract stats
        stats = dg.stats
        if abs(0.5 - stats.score) < trueskill.DRAW_MARGIN:
            winner = "draw"
        elif stats.score > 0.5:
            winner = "red"
        else:
            winner = "blue"
        # Truncate game log if needed
        log = str(dg.log)
        if len(log) > 16*1024:
            msg = "\n== LOG TRUNCATED ==\n"
            log = log[:16*1024-len(msg)] + msg
        # Adjust agent scores:
        logging.info("Storing game.")
        # Compute new scores
        red_new, blue_new = trueskill.adjust((red.score, red.uncertainty), 
                                 (blue.score, blue.uncertainty), draw=(winner=="draw"))
        red.played_game(red_new, error=dg.red_raised_exception)
        blue.played_game(blue_new, error=dg.blue_raised_exception)
        # Store stuff
        game = cls(red=red, 
                   blue=blue,
                   score_red=stats.score_red,
                   score_blue=stats.score_blue,
                   error_red=dg.red_raised_exception,
                   error_blue=dg.blue_raised_exception,
                   stats=repr(dg.stats.__dict__), 
                   winner=winner,
                   log=log, group=red.group, parent=red.group)
        def txn():
            game.put()
            red.put()
            blue.put()
        db.run_in_transaction(txn)
        logging.info("Game was put.")
        
    def url(self):
        return reverse("dominationgame.views.game", args=[self.group.slug, self.key().id()])
        