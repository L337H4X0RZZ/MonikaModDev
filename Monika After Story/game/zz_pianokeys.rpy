# Module that lets you play the piano
#

# TRANSFORMS
transform piano_quit_label:
    xanchor 0.5 xpos 275 yanchor 0 ypos 332

transform piano_lyric_label:
    xalign 0.5 yalign 0.5

# label that calls this creen
label zz_play_piano:
    m 1j "You want to play the piano?"
    m 1a "Then play for me, [player]..."
    show monika 1a at t22

    # pre call setup
    python:
        quit_label = Text("Press 'Z' to quit", size=36) 
        disable_esc()
        store.songs.enabled = False
        store.hkb_button.enabled = False
    stop music
    show text quit_label zorder 10 at piano_quit_label

    # call the display
    $ ui.add(PianoDisplayable())
    $ result = ui.interact()

    # post call cleanup
    hide text quit_label
    $ store.songs.enabled = True
    $ store.hkb_button.enabled = True
    $ enable_esc()
    $ play_song(store.songs.selected_track)

    show monika 1j at t11
    m 1j "That was wonderful, [player]!"
    return

# keep the above for reference
# DISPLAYABLE:

# this is our threshold for determining how many notes the player needs to play
# before we check for dialogue
define zzpk.NOTE_SIZE = 6 

init python:
    import pygame # because we need them keyups 

    # Exception class for piano failures
    class PianoException(Exception):
        def __init__(self, msg):
            self.msg = msg
        def __str__(self):
            return "PianoException: " + self.msg

    # this class matches particular sets of notes to some dialogue that 
    # Monika can say.
    # NOTE: only one line of dialogue per set of notes, because brevity is
    #   important
    #
    # PROPERTIES:
    #   say - the line of dialogue to say (as a Text object)
    #   notes - list of notes (keys) that we need to hear to show the dialogue
    #       this is ORDER match only. also chords are NOT supported
    #       NOTE: This is expected as a list of ZZPK constants.
    #   notestr - string version of the list of notes, for matching
    #   express - the expression we want monika to show (prefixed with monika)
    #   matched - True if we were matched this session, False otherwise
    #   matchdex - Basically an index that says where the last matched note is
    #       in notestr (and notes, by extension)
    #   timeout - number of seconds before the dialogue should be removed
    #       after a match is done
    #   fails - number of failed attempts to play this
    #   passes - number of succesful attempts to play this
    #   postnotes - list of notes (keys) that are considered post match.
    #       NOTE: so if this is played after the match, monika will continue
    #           her expression until a miss or the set is complete.
    #           in both cases, we should expect a clearing of played
    #   postexpress - expression monika should have during post mode
    #
    class PianoNoteMatch():
        def __init__(self, 
                say, 
                notes, 
                postnotes=None, 
                express="1b", 
                postexpress="1a",
                timeout=0
            ):
            #
            # IN:
            #   say - line of dialogue to say (as a Text object)
            #   notes - list of notes (keys) to match 
            #   postnotes - list of notes (keys) that are considered post
            #       match
            #       (Default: None)
            #   express - the monika expression we want to show
            #       (Default: 1b)
            #   postexpress - the monika expression to show during post
            #       (Default: 1a)
            #   timeout - the number of seconds the dialogue should display
            #       after matches stop
            #       (Default: 0)

            if notes is None or len(notes) < zzpk.NOTE_SIZE:
                raise PianoException(
                    "Notes list must be longer than " + str(zzpk.NOTE_SIZE)
                )
            if timeout < 0:
                raise PianoException("Timeout must be positive number")
            if type(say) is not Text:
                raise PianoException("say must be of type Text")
            if not renpy.image_exists("monika " + express):
                raise PianoException("Given expression does not exist")
            if not renpy.image_exists("monika " + postexpress):
                raise PianoException("Given post expression does not exist")

            self.say = say
            self.notes = notes
            self.notestr = "".join([chr(x) for x in notes])
            self.express = "monika " + express
            self.matched = False
            self.matchdex = 0
            self.timeout = timeout
            self.fails = 0
            self.passes = 0
            self.postnotes = postnotes
            self.postexpress = "monika " + postexpress

        def isNoteMatch(self, new_key, index=None):
            #
            # Checks if the new key continous a notes match
            #
            # IN:
            #   new_key - the key we want to check (pygame key)
            #   index - current index we need to look at
            #       (Default: self.matchdex)
            #
            # OUT:
            #   returns 1 or larger if we have a match
            #       -1 if no match
            #       -2 if index out of range
            
            return self._is_match(new_key, self.notes, index=index)

        def isPostMatch(self, new_key, index=None):
            #
            # Checks if the new key continous a post match
            #
            # IN:
            #   new_key - the key we want to check (pygame key)
            #   index - current index we need to look at
            #       (Default: self.matchdex)
            #
            # OUT:
            #   returns 1 or large if we have a match
            #       -1 if no match
            #       -2 if index out of range

            return self._is_match(new_key, self.postnotes, index=index)

        def _is_match(self, new_key, notes, index=None):
            #
            # checks if the new key continous the match that we are expecting
            #
            # IN:
            #   new_key - the key we want to check (pygame key)
            #   notes - the notes list we want to look at
            #   index - current index we need to look at
            #       (Default: self.matchdex)
            #
            # OUT:
            #   returns 1 or larger if we have a match
            #       -1 if no match
            #       -2 if index out of range
        
            if index is None:
                index = self.matchdex

            if index >= len(notes):
                return -2

            if new_key == notes[index]:
                self.matchdex = index + 1
                return 1

            return -1

    # the displayable
    class PianoDisplayable(renpy.Displayable):

        # CONSTANTS
        # timeout
        TIMEOUT = 1.0 # seconds
        SONG_TIMEOUT = 2.0 # seconds
        SONG_VIS_TIMEOUT = 4.0 # seconds
#        FAIL_TIMEOUT = 4.0 # number of seconds to display awkward face on fail
#        MISS_TIMEOUT = 4.0 # number of seconds to display awkard face on miss
#        MATCH_TIMEOUT = 4.0 # number of seconds to wait for match notes
        VIS_TIMEOUT = 2.5 # number of seconds to wait before changing face
        

        # AT_LIST 
        AT_LIST = [i22]
        TEXT_AT_LIST = [piano_lyric_label]

        # expressions
        DEFAULT = "monika 1a"
        AWKWARD = "monika 1l"
        HAPPY = "monika 1j"
        FAILED = "monika 1m"

        # Text related
        TEXT_TAG = "piano_text"

        # STATEMACHINE STUFF
        STATE_LISTEN = 0 # default state
        STATE_JMATCH = 1 # we matched a note
        STATE_MATCH = 2 # currently matching a phrase
        STATE_MISS = 3 # you missed a note
        STATE_FAIL = 4 # you failed a phrase
        STATE_JPOST = 5 # we just entered post match
        STATE_POST = 6 # post match state, where we match post notes 
        STATE_VPOST = 7 # only visual post match, until next key is hit or time
        STATE_WPOST = 8 # waitin post-state
        STATE_CLEAN = 9 # reset things

        # key limit for matching
        KEY_LIMIT = 100

        # keys
        ZZPK_QUIT = pygame.K_z
        ZZPK_F4 = pygame.K_q
        ZZPK_F4SH = pygame.K_2
        ZZPK_G4 = pygame.K_w
        ZZPK_G4SH = pygame.K_3
        ZZPK_A4 = pygame.K_e
        ZZPK_A4SH = pygame.K_4
        ZZPK_B4 = pygame.K_r
        ZZPK_C5 = pygame.K_t
        ZZPK_C5SH = pygame.K_6
        ZZPK_D5 = pygame.K_y
        ZZPK_D5SH = pygame.K_7
        ZZPK_E5 = pygame.K_u
        ZZPK_F5 = pygame.K_i
        ZZPK_F5SH = pygame.K_9
        ZZPK_G5 = pygame.K_o
        ZZPK_G5SH = pygame.K_0
        ZZPK_A5 = pygame.K_p
        ZZPK_A5SH = pygame.K_MINUS
        ZZPK_B5 = pygame.K_LEFTBRACKET
        ZZPK_C6 = pygame.K_RIGHTBRACKET

        # keyorder, for reference
        ZZPK_KEYORDER = [
            ZZPK_F4,
            ZZPK_F4SH,
            ZZPK_G4,
            ZZPK_G4SH,
            ZZPK_A4,
            ZZPK_A4SH,
            ZZPK_B4,
            ZZPK_C5,
            ZZPK_C5SH,
            ZZPK_D5,
            ZZPK_D5SH,
            ZZPK_E5,
            ZZPK_F5,
            ZZPK_F5SH,
            ZZPK_G5,
            ZZPK_G5SH,
            ZZPK_A5,
            ZZPK_A5SH,
            ZZPK_B5,
            ZZPK_C6
        ]

        # filenames
        ZZFP_F4 =  "mod_assets/sounds/piano_keys/F4.ogg"
        ZZFP_F4SH = "mod_assets/sounds/piano_keys/F4sh.ogg"
        ZZFP_G4 = "mod_assets/sounds/piano_keys/G4.ogg"
        ZZFP_G4SH = "mod_assets/sounds/piano_keys/G4sh.ogg"
        ZZFP_A4 = "mod_assets/sounds/piano_keys/A4.ogg"
        ZZFP_A4SH = "mod_assets/sounds/piano_keys/A4sh.ogg"
        ZZFP_B4 = "mod_assets/sounds/piano_keys/B4.ogg"
        ZZFP_C5 = "mod_assets/sounds/piano_keys/C5.ogg"
        ZZFP_C5SH = "mod_assets/sounds/piano_keys/C5sh.ogg"
        ZZFP_D5 = "mod_assets/sounds/piano_keys/D5.ogg"
        ZZFP_D5SH = "mod_assets/sounds/piano_keys/D5sh.ogg"
        ZZFP_E5 = "mod_assets/sounds/piano_keys/E5.ogg"
        ZZFP_F5 = "mod_assets/sounds/piano_keys/F5.ogg"
        ZZFP_F5SH = "mod_assets/sounds/piano_keys/F5sh.ogg"
        ZZFP_G5 = "mod_assets/sounds/piano_keys/G5.ogg"
        ZZFP_G5SH = "mod_assets/sounds/piano_keys/G5sh.ogg"
        ZZFP_A5 = "mod_assets/sounds/piano_keys/A5.ogg"
        ZZFP_A5SH = "mod_assets/sounds/piano_keys/A5sh.ogg"
        ZZFP_B5 = "mod_assets/sounds/piano_keys/B5.ogg"
        ZZFP_C6 = "mod_assets/sounds/piano_keys/C6.ogg"

        # piano images
        ZZPK_IMG_BACK = "mod_assets/piano/board.png"
        ZZPK_IMG_KEYS = "mod_assets/piano/piano.png"

        # lyrical bar
        ZZPK_LYR_BAR = "mod_assets/piano/lyrical_bar.png"

        # overlay, white
        ZZPK_W_OVL_LEFT = "mod_assets/piano/ovl/ivory_left.png"
        ZZPK_W_OVL_RIGHT = "mod_assets/piano/ovl/ivory_right.png"
        ZZPK_W_OVL_CENTER = "mod_assets/piano/ovl/ivory_center.png"
        ZZPK_W_OVL_PLAIN = "mod_assets/piano/ovl/ivory_plain.png"
        
        # overlay black
        ZZPK_B_OVL_PLAIN = "mod_assets/piano/ovl/ebony.png"

        # offsets for rendering
        ZZPK_IMG_BACK_X = 5
        ZZPK_IMG_BACK_Y = 10
        ZZPK_IMG_KEYS_X = 51
        ZZPK_IMG_KEYS_Y = 50
        ZZPK_LYR_BAR_YOFF = -50
        
        # other sizes
        ZZPK_IMG_IKEY_WIDTH = 36
        ZZPK_IMG_IKEY_HEIGHT = 214
        ZZPK_IMG_EKEY_WIDTH = 29
        ZZPK_IMG_EKEY_HEIGHT = 152
        
        def __init__(self):
            super(renpy.Displayable,self).__init__()

            # setup images

            # background piano
            self.piano_back = Image(self.ZZPK_IMG_BACK)
            self.piano_keys = Image(self.ZZPK_IMG_KEYS)
            self.PIANO_BACK_WIDTH = 437
            self.PIANO_BACK_HEIGHT = 214

            # lyric bar
            self.lyrical_bar = Image(self.ZZPK_LYR_BAR)

            # setup sounds
            # sound dict:
            self.pkeys = {
                self.ZZPK_F4: self.ZZFP_F4,
                self.ZZPK_F4SH: self.ZZFP_F4SH,
                self.ZZPK_G4: self.ZZFP_G4,
                self.ZZPK_G4SH: self.ZZFP_G4SH,
                self.ZZPK_A4: self.ZZFP_A4,
                self.ZZPK_A4SH: self.ZZFP_A4SH,
                self.ZZPK_B4: self.ZZFP_B4,
                self.ZZPK_C5: self.ZZFP_C5,
                self.ZZPK_C5SH: self.ZZFP_C5SH,
                self.ZZPK_D5: self.ZZFP_D5,
                self.ZZPK_D5SH: self.ZZFP_D5SH,
                self.ZZPK_E5: self.ZZFP_E5,
                self.ZZPK_F5: self.ZZFP_F5,
                self.ZZPK_F5SH: self.ZZFP_F5SH,
                self.ZZPK_G5: self.ZZFP_G5,
                self.ZZPK_G5SH: self.ZZFP_G5SH,
                self.ZZPK_A5: self.ZZFP_A5,
                self.ZZPK_A5SH: self.ZZFP_A5SH,
                self.ZZPK_B5: self.ZZFP_B5,
                self.ZZPK_C6: self.ZZFP_C6
            }

            # pressed dict
            self.pressed = {
                self.ZZPK_F4: False,
                self.ZZPK_F4SH: False,
                self.ZZPK_G4: False,
                self.ZZPK_G4SH: False,
                self.ZZPK_A4: False,
                self.ZZPK_A4SH: False,
                self.ZZPK_B4: False,
                self.ZZPK_C5: False,
                self.ZZPK_C5SH: False,
                self.ZZPK_D5: False,
                self.ZZPK_D5SH: False,
                self.ZZPK_E5: False,
                self.ZZPK_F5: False,
                self.ZZPK_F5SH: False,
                self.ZZPK_G5: False,
                self.ZZPK_G5SH: False,
                self.ZZPK_A5: False,
                self.ZZPK_A5SH: False,
                self.ZZPK_B5: False,
                self.ZZPK_C6: False
            }

            # overlay setup
            left = Image(self.ZZPK_W_OVL_LEFT)
            right = Image(self.ZZPK_W_OVL_RIGHT)
            center = Image(self.ZZPK_W_OVL_CENTER)
            w_plain = Image(self.ZZPK_W_OVL_PLAIN) 
            whites = [
                (self.ZZPK_F4, left),
                (self.ZZPK_G4, center),
                (self.ZZPK_A4, center),
                (self.ZZPK_B4, right),
                (self.ZZPK_C5, left),
                (self.ZZPK_D5, center),
                (self.ZZPK_E5, right),
                (self.ZZPK_F5, left),
                (self.ZZPK_G5, center),
                (self.ZZPK_A5, center),
                (self.ZZPK_B5, right),
                (self.ZZPK_C6, w_plain),
            ]

            # key, x coord
            # NOTE: this is differente because black keys are not separated
            # equally
            b_plain = Image(self.ZZPK_B_OVL_PLAIN)
            blacks = [
                (self.ZZPK_F4SH, 73),
                (self.ZZPK_G4SH, 110),
                (self.ZZPK_A4SH, 147),
                (self.ZZPK_C5SH, 221),
                (self.ZZPK_D5SH, 258),
                (self.ZZPK_F5SH, 332),
                (self.ZZPK_G5SH, 369),
                (self.ZZPK_A5SH, 406)
            ]

            # overlay dict
            # NOTE: x and y are assumed to be relative to the top let of
            #   the piano_back image
            # (overlay image, x coord, y coord)
            self.overlays = dict()

            # white overlay processing
            for i in range(0,len(whites)):
                k,img = whites[i]
                self.overlays[k] = (
                    img,
                    self.ZZPK_IMG_KEYS_X + (i * (self.ZZPK_IMG_IKEY_WIDTH + 1)),
                    self.ZZPK_IMG_KEYS_Y
                )

            # blacks overlay processing
            for k,x in blacks:
                self.overlays[k] = (
                    b_plain,
                    x,
                    self.ZZPK_IMG_KEYS_Y
                )

            # your reality, note matching
            # NOTE: This works by peforming `in` matches of lists.
            self.pnm_yourreality = [
                PianoNoteMatch(
                    Text(
                        "Everyday, I imagine a future where I can be with you",
                        style="monika_credits_text"
                    ),
                    [
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_F5,
                        self.ZZPK_E5,
                        self.ZZPK_E5,
                        self.ZZPK_F5,
                        self.ZZPK_G5,
                        self.ZZPK_E5,
                        self.ZZPK_D5,
                        self.ZZPK_C5,
                        self.ZZPK_D5,
                        self.ZZPK_E5,
                        self.ZZPK_C5,
                        self.ZZPK_G4
                    ],
                    postnotes=[
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_C6,
                        self.ZZPK_C6,
                        self.ZZPK_A5,
                        self.ZZPK_B5,
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_B5,
                        self.ZZPK_G5
                    ],
                    express="1k",
                    postexpress="1j"
                ),
                PianoNoteMatch(
                    Text(
                        ("In my hands, is a pen that will write a poem of me" +
                        " and you"),
                        style="monika_credits_text"
                    ),
                    [
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_E5,
                        self.ZZPK_F5,
                        self.ZZPK_G5,
                        self.ZZPK_F5,
                        self.ZZPK_E5,
                        self.ZZPK_D5,
                        self.ZZPK_A4,
                        self.ZZPK_G4,
                        self.ZZPK_F4,
                        self.ZZPK_A4,
                        self.ZZPK_G4,
                        self.ZZPK_E5,
                        self.ZZPK_C5
                    ],
                    postnotes=[
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_C6,
                        self.ZZPK_C6,
                        self.ZZPK_A5,
                        self.ZZPK_B5,
                        self.ZZPK_G5,
                        self.ZZPK_A5,
                        self.ZZPK_B5,
                        self.ZZPK_G5
                    ],
                    express="1b",
                    postexpress="1a"
                ),
                PianoNoteMatch(
                    Text(
                        "The ink flows down into a dark puddle",
                        style="monika_credits_text"
                    ),
                    [
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_G5,
                        self.ZZPK_F5,
                        self.ZZPK_E5,
                        self.ZZPK_C5,
                        self.ZZPK_C5,
                        self.ZZPK_D5,
                        self.ZZPK_E5,
                        self.ZZPK_G5
                    ],
                    express="1b",
                    postexpress="1a"
                ),
                PianoNoteMatch(
                    Text(
                        "Just move your hands - write the way into his heart",
                        style="monika_credits_text"
                    ),
                    [
                        self.ZZPK_A5,
                        self.ZZPK_G5,
                        self.ZZPK_E5,
                        self.ZZPK_D5,
                        self.ZZPK_G4,
                        self.ZZPK_A4,
                        self.ZZPK_C5,
                        self.ZZPK_A4,
                        self.ZZPK_C5,
                        self.ZZPK_D5,
                        self.ZZPK_C5
                    ],
                    express="1k",
                    postexpress="1j"
                )
            ]

            # list containing lists of matches. 
            # NOTE: highly recommend not adding too many detections
            self.pnm_list = [
                self.pnm_yourreality
            ]

            # list of notes we have played
            self.played = list()
            self.prev_time = 0
            
            # currently matched dialogue
            self.match = None

            # True if we literally just matched, False if not
            self.justmatched = False 

            # true only if we had a missed match, after a match
            self.missed_one = False

            # contains the previously matched pnm
            self.lastmatch = None

            # true if we failed the last match
            # NOTE: this should be reset by timeout, also when match is found
            self.failed = False

            # NOTE: the current state
            self.state = self.STATE_LISTEN

            # currently visible text
            self.lyric = None

            # what index of piano matching should we be looking at
            self.pnm_index = 0

            # timeouts
            self.ev_timeout = self.TIMEOUT
            self.vis_timeout = self.VIS_TIMEOUT

            # DEBUG: NOTE:
            self.testing = open("piano", "w+")

        def findnotematch(self, notes):
            #
            # Finds a PianoNoteMatch object that matches the given set of
            # notes.
            #
            # IN:
            #   notes - list of notes to match
            #
            # RETURNS:
            #   PianoNoteMatch object that matches, or None if no match

            # convert to string for ease of us
            notestr = "".join([chr(x) for x in notes])

            for index in range(0, len(self.pnm_yourreality)):
                pnm = self.pnm_yourreality[index]
                findex = pnm.notestr.find(notestr)
                if findex >= 0:
                    pnm.matchdex = findex + len(notestr)
                    pnm.matched = True
                    self.pnm_index = index
                    return pnm

            return None

        def getnotematch(self, index=None):
            #
            # returns the notematch object at the given index
            # 
            # IN:
            #   index - the index to retrieve notematch.
            #       If None, the self.pnm_index is incremeneted and used as
            #       the index
            #
            # OUT:
            #   returns PianoNoteMatch object at index, or None if index is
            #   beyond the grave

            if index is None:
                self.pnm_index += 1
                index = self.pnm_index

            if index >= len(self.pnm_yourreality):
                return None

            return self.pnm_yourreality[index]

        def setsongmode(self, songmode=True):
            #
            # sets our timeout vars into song mode
            #
            # IN:
            #   songmode - True means set into song mode, False means get out
            #       (Default: True)

            if songmode:
                self.ev_timeout = self.SONG_TIMEOUT
                self.vis_timeout = self.SONG_VIS_TIMEOUT
            else:
                self.ev_timeout = self.TIMEOUT
                self.vis_timeout = self.VIS_TIMEOUT

        def render(self, width, height, st, at):
            # renpy render function
            # NOTE: Displayables are EVENT-DRIVEN

            r = renpy.Render(width, height)

            # prepare piano back as render
            back = renpy.render(self.piano_back, 1280, 720, st, at)
            piano = renpy.render(self.piano_keys, 1280, 720, st, at)
            

            # now prepare overlays to render
            overlays = list()
            for k in self.pressed:
                if self.pressed[k]:
                    overlays.append(
                        (
                            renpy.render(self.overlays[k][0], 1280, 720, st, at),
                            self.overlays[k][1],
                            self.overlays[k][2]
                        )
                    )

            # Draw the piano
            r.blit(
                back,
                (
                    self.ZZPK_IMG_BACK_X,
                    self.ZZPK_IMG_BACK_Y
                )
            )
            r.blit(
                piano, 
                (
                    self.ZZPK_IMG_KEYS_X + self.ZZPK_IMG_BACK_X, 
                    self.ZZPK_IMG_KEYS_Y + self.ZZPK_IMG_BACK_Y
                )
            )

            # and now the overlays
            for ovl in overlays:
                r.blit(
                    ovl[0], 
                    (
                        self.ZZPK_IMG_BACK_X + ovl[1],
                        self.ZZPK_IMG_BACK_Y + ovl[2]
                    )
                )

            # preprocessing for timeouts
            if st-self.prev_time >= self.vis_timeout:
                self.state = self.STATE_CLEAN

            # True if we need to do an interaction restart
            restart_int = False

            # check if we are currently matching something
            # NOTE: the following utilizies renpy.show, which means we need
            #   to use renpy.restart_interaction(). This also means that the
            #   changes that occur here shouldnt be rendered
            # STATE MACHINE
            if self.state == self.STATE_CLEAN:

                # default monika
                renpy.show(self.DEFAULT)

                # hide text
                self.lyric = None

                restart_int = True
                self.state = self.STATE_LISTEN
                self.setsongmode(False)

            elif self.state != self.STATE_LISTEN:

                if self.state == self.STATE_JMATCH:

                    # display monika's expression
                    renpy.show(self.match.express)
                    
                    # display text
                    self.lyric = self.match.say

                    restart_int = True
                    self.state = self.STATE_MATCH

                elif self.state == self.STATE_MISS:

                    # display an awkward expresseion monika
                    renpy.show(self.AWKWARD)
                    restart_int = True

                elif self.state == self.STATE_VPOST:
                    
                    # display the post expression
                    if self.match.postexpress:
                        renpy.show(self.match.postexpress)
                        restart_int = True

                    # hide text
                    self.lyric = None
                    self.state = self.STATE_WPOST

                elif self.state == self.STATE_JPOST:
                    
                    # display monikas post expression
                    renpy.show(self.match.postexpress)

                    # hide text
                    self.lyric = None

                    restart_int = True
                    self.state = self.STATE_POST

                elif self.state == self.STATE_FAIL:

                    # display failed monika
                    renpy.show(self.FAILED)

                    # hide text
                    self.lyric = None

                    restart_int = True
                    self.state = self.STATE_CLEAN

                # redraw timeout
                renpy.redraw(self, self.VIS_TIMEOUT)


            if self.lyric:
                lyric_bar = renpy.render(self.lyrical_bar, 1280, 720, st, at)
                lyric = renpy.render(self.lyric, 1280, 720, st, at)
                pw, ph = lyric.get_size()
                r.blit(
                    lyric_bar,
                    (
                        0,
                        int((height - 50) /2) - self.ZZPK_LYR_BAR_YOFF
                    )
                )
                r.blit(
                    lyric,
                    (
                        int((width - pw) / 2),
                        int((height - ph) / 2) - self.ZZPK_LYR_BAR_YOFF
                    )
                )

#                    renpy.show(
#                        "monika " + match.express,
#                        at_list=self.AT_LIST,
#                        zorder=10,
#                        layer="transient"
#                    )
#                    renpy.force_full_redraw()
#                    r.blit(
#                        renpy.render(match.img, 1280, 720, st, at),
#                        (0, 0)
#                    )
#                    renpy.say(m, match.say, interact=False)
#                    renpy.force_full_redraw()

            if restart_int:
                renpy.restart_interaction()

            # rerender redrawing thing
            # renpy.redraw(self, 0)

            # and apparenly we return the render object
            return r

        def event(self, ev, x, y, st):
            # renpy event handler
            # NOTE: Renpy is EVENT-DRIVEN

            # when you press down a key, we launch a sound
            if ev.type == pygame.KEYDOWN:

                if len(self.played) > self.KEY_LIMIT:
                    self.played = list()

                # we only care about keydown events regarding timeout
                elif st-self.prev_time >= self.ev_timeout:

#                    self.testing.write("".join([chr(x) for x in self.played])+ "\n")
                    self.played = list()

                    if self.state != self.STATE_LISTEN:
                        self.state = self.STATE_CLEAN
                        renpy.redraw(self, 0)

#   DEBUG: NOTE:
#                if self.match:
#                    self.testing.write(
#                        chr(ev.key) + " : " + str(self.state) + " : " +
#                        str(self.match.matchdex) + "\n")
#                else:
#                    self.testing.write(chr(ev.key) + " : " + str(self.state) + "\n")

                # setup previous time thing
                self.prev_time = st

                # but first, check for quit ("Z")
                if ev.key == self.ZZPK_QUIT:
                    return "q" # quit this game
                else:

                    # only play a sound if we've lifted the finger
                    if not self.pressed.get(ev.key, True):

                        # add to played
                        self.played.append(ev.key)

                        # set appropriate value
                        self.pressed[ev.key] = True

                        # check if we have enough played notes
                        if (
                                self.state == self.STATE_LISTEN
                                and len(self.played) >= zzpk.NOTE_SIZE
                            ):
                            self.match = self.findnotematch(self.played)

                            # check if match
                            if self.match:
                                self.state = self.STATE_JMATCH

                        # post match checking
                        elif self.state == self.STATE_POST:
                            # post match means we abort on the first miss
                            findex = self.match.isPostMatch(ev.key)

                            # abort post
                            if findex == -1:
                                self.state = self.STATE_CLEAN
                                self.played = [ev.key]

                            # successful post
                            elif self.match.matchdex == len(self.match.postnotes):
                                
                                next_pnm = self.getnotematch()

                                # check next set of notes
                                if next_pnm:

                                    self.match = next_pnm
                                    self.state = self.STATE_WPOST
                                    self.played = list()
                                    self.setsongmode()

                                # abourt please
                                else:
                                    self.state = self.STATE_CLEAN

                        # waiting post
                        elif self.state == self.STATE_WPOST:
                            # here we check the just hit note for matching
                            findex = self.match.isNoteMatch(ev.key, index=0)

                            if findex > 0:
                                self.state = self.STATE_JMATCH

                            else:
                                self.state = self.STATE_CLEAN
                                self.played = [ev.key]

                        # preprocess match
                        elif (
                                self.state == self.STATE_MATCH
                                or self.state == self.STATE_MISS
                                or self.state == self.STATE_JMATCH
                            ):
                            # we have a match, check to ensure that this key
                            # follows the pattern
                            findex = self.match.isNoteMatch(ev.key)

                            # failed match
                            if findex < 0:

                                # -1 is a non match
                                if findex == -1:

                                    # check for a double failure, which means
                                    # we failed entirely on playing this piece
                                    if self.state == self.STATE_MISS:
                                        self.match.fails += 1
                                        self.state = self.STATE_FAIL

                                        # incase of a double failure, we zero
                                        # the list and the prev time
                                        self.played = [ev.key]

                                        # clear the match
 #                                       self.lastmatch = None
 #                                       self.match = None

                                    # this is our first failure, just take note
                                    else:
                                        self.state = self.STATE_MISS

                            # otherwise, we matched, but need to clear fails
                            else:

                                # check for finished notes
                                if self.match.matchdex == len(self.match.notes):

                                    # you passed
                                    self.match.passes += 1

                                    # post notes flow
                                    if self.match.postnotes:
                                        self.state = self.STATE_JPOST
                                        self.match.matchdex = 0

                                    # next pnm match
                                    else:
                                        next_pnm = self.getnotematch()

                                        if next_pnm:

                                            self.match = next_pnm
                                            self.state = self.STATE_VPOST
                                            self.setsongmode()
                                            self.match.matchdex = 0
                                            self.played = list()

                                        else:
                                            self.state = self.STATE_CLEAN

                                else:
                                    self.state = self.STATE_MATCH

                        # get a sound to play
                        renpy.play(self.pkeys[ev.key], channel="audio")

                        # now rerender
                        renpy.redraw(self, 0)

            # keyup, means we should stop render
            elif ev.type == pygame.KEYUP:

                # only do this if we keyup a key we care about
                if self.pressed.get(ev.key, False):

                    # set appropriate value
                    self.pressed[ev.key] = False

                    # now rerender
                    renpy.redraw(self,0)

            # the default so we can keep going
            raise renpy.IgnoreEvent()
