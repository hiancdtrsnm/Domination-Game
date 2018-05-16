
from domination import core

# Make it a short game
settings = core.Settings(max_steps=100000, max_score=1000)

# Initialize a game
game = core.Game('domination/agent.py', 'shareinfo.py',
                 record=True, rendered=False, settings=settings)
# game = core.Game('newagent.py', 'randomAgent.py',
#                  record=True, rendered=False, settings=settings)
# Will run the entire game.
game.run()
# And now let's see the replay!
replay = game.replay
playback = core.Game(replay=replay)
playback.run()
