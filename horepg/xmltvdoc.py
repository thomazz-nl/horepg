import xml.dom.minidom
import time
import logging
import re

def debug(msg):
  logging.debug(msg)

def info(msg):
  logging.info(msg)

def sanitize_channel_id(channel_id):
  # To pass XMLTV validation, the primary goal is to adhere to the xmltv.dtd (https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.dtd).
  # But XMLTV often (e.g. tv_validate_file) performs additional validation against a more strict Perl ValidateFile.pm file (https://raw.githubusercontent.com/XMLTV/xmltv/master/lib/ValidateFile.pm).
  # The "channel id" definition in the DTD is comfortably loose although they suggest the RFC2838 format (https://tools.ietf.org/html/rfc2838).
  # The "channel id" definition of ValidateFile.pm enforces a format according to this regex /^[-a-zA-Z0-9]+(\.[-a-zA-Z0-9]+)+$/ which does not match a RFC2838 format.
  # Both validations do seem to approve the regex format, so let's stick to that.
  channel_id_spec = re.compile('^[-a-zA-Z0-9]+(\.[-a-zA-Z0-9]+)+$')
  sanitized_channel_name = channel_id.replace('_', '-').replace(':', '.')
  return sanitized_channel_name if re.match(channel_id_spec, sanitized_channel_name) else channel_id

class XMLTVDocument(object):
  # this renames some of the channels
  replace_display_name = {
    #'sample channel name HD': [ 'sample channel name', 'some other name' ]
  }

  # Target names taken from: https://github.com/tvheadend/tvheadend/blob/fdc3f945f2b759a743a595b134786b881538f52e/src/epg.c#L1741
  # All entries must be lower case
  # Sorted alphabetically by value, key (for maintenance sake)
  category_map = {
    # 00
    'event': '',        # Used for various categories
    'miniseries': '',   # Format, not content
    'onbepaald': '',

    # 01
    'erotiek': 'adult movie/drama',
    'erotisch': 'adult movie/drama',
    'avontuur': 'adventure/western/war',
    'western': 'adventure/western/war',
    'komedie': 'comedy',
    'sitcoms': 'comedy',
    'standup komedie': 'comedy',
    'zwarte komedie': 'comedy',
    'detective': 'detective/thriller',
    'misdaaddrama': 'detective/thriller',
    'mysterie': 'detective/thriller',
    'thriller': 'detective/thriller',
    'actie': 'movie/drama',
    'dramaseries': 'movie/drama',
    'familie': 'movie/drama',
    'film': 'movie/drama',
    'film/cinema': 'movie/drama',
    'speelfilm': 'movie/drama',
    'tv drama': 'movie/drama',
    'romantiek': 'romance',
    'romantisch': 'romance',
    'romantische komedie': 'romance',
    'fantasy': 'science fiction/fantasy/horror',
    'horror': 'science fiction/fantasy/horror',
    'sci-fi': 'science fiction/fantasy/horror',
    'sci-fi/horror': 'science fiction/fantasy/horror',
    'sciencefiction': 'science fiction/fantasy/horror',
    'drama': 'serious/classical/religious/historical movie/drama',
    'historisch drama': 'serious/classical/religious/historical movie/drama',
    'melodrama': 'soap/melodrama/folkloric',
    'soap': 'soap/melodrama/folkloric',

    # 02
    'debat': 'discussion/interview/debate',
    'discussie': 'discussion/interview/debate',
    'interview': 'discussion/interview/debate',
    'docudrama': 'documentary',
    'documentaire': 'documentary',
    'docusoap': 'documentary',
    'geschiedenis': 'documentary',
    'historisch': 'documentary',
    'waar gebeurd': 'documentary',
    'nieuws documentaire': 'news magazine',
    'actualiteit': 'news/current affairs',
    'actualiteitenprogramma\'s': 'news/current affairs',
    'nieuws': 'news/current affairs',
    'weer': 'news/weather report',

    # 03
    #'': 'game show/quiz/contest',
    'awards': 'show/game show',
    'entertainment': 'show/game show',
    'show': 'show/game show',
    'spelshow': 'show/game show',
    'talk show': 'talk show',
    'talkshow': 'talk show',
    'bloemlezing': 'variety show',
    'theater': 'variety show',
    'variete': 'variety show',
    'variété': 'variety show',

    # 04
    'atletiek': 'athletics',
    'turnen': 'athletics',
    'paardensport': 'equestrian',
    'polo': 'equestrian',
    'american football': 'football/soccer',
    'voetbal': 'football/soccer',
    'boksen': 'martial sports',
    'gevechtssport': 'martial sports',
    'judo': 'martial sports',
    'mixed martial arts (mma)': 'martial sports',
    'schermen': 'martial sports',
    'vechtsporten': 'martial sports',
    'worstelen': 'martial sports',
    'motorracen': 'motor sport',
    'motors': 'motor sport',
    'motorsport': 'motor sport',
    'evenementen': 'special events (olympic games, world cup, etc.)',
    'olympische spelen': 'special events (olympic games, world cup, etc.)',
    'sportmagazine': 'sports magazines',
    'sporttalkshow': 'sports magazines',
    'beachvolleybal': 'sports',
    'biathlon': 'sports',
    'biljart': 'sports',
    'boogschieten': 'sports',
    'competitiesporten': 'sports',
    'curling': 'sports',
    'darts': 'sports',
    'esports': 'sports',
    'extreme': 'sports',
    'extreme sporten': 'sports',
    'gamen': 'sports',
    'gewichtheffen': 'sports',
    'golf': 'sports',
    'ijshockey': 'sports',
    'kunstschaatsen': 'sports',
    'marathon': 'sports',
    'mountainbiken': 'sports',
    'pool': 'sports',
    'running': 'sports',
    'schietsport': 'sports',
    'skateboarden': 'sports',
    'snooker': 'sports',
    'sport': 'sports',
    'stierenvechten': 'sports',
    'tafeltennis': 'sports',
    'tennis': 'sports',
    'triathlon': 'sports',
    'vliegsport': 'sports',
    'basketbal': 'team sports (excluding football)',
    'cricket': 'team sports (excluding football)',
    'handbal': 'team sports (excluding football)',
    'hockey': 'team sports (excluding football)',
    'rugby league': 'team sports (excluding football)',
    'rugby union': 'team sports (excluding football)',
    'rugby': 'team sports (excluding football)',
    'teamsporten': 'team sports (excluding football)',
    'volleybal': 'team sports (excluding football)',
    'wielrennen': 'team sports (excluding football)',
    'tennis/squash': 'tennis/squash',
    'duiken': 'water sport',
    'kanoën': 'water sport',
    'kunstzwemmen': 'water sport',
    'roeien': 'water sport',
    'surfen': 'water sport',
    'water polo': 'water sport',
    'watersport': 'water sport',
    'zeilen': 'water sport',
    'zeilracen': 'water sport',
    'zwemmen': 'water sport',
    'alpineskiën': 'winter sports',
    'freestyle skiën': 'winter sports',
    'skispringen': 'winter sports',
    'skiën': 'winter sports',
    'snowboarden': 'winter sports',
    'wintersport': 'winter sports',

    # 05
    'animatie': 'cartoons/puppets',
    'anime': 'cartoons/puppets',
    'poppenspel': 'cartoons/puppets',
    'kids/jeugd': 'children\'s/youth programs',
    'kinderen': 'children\'s/youth programs',
    'jeugd 10 - 16': 'entertainment programs for 10 to 16',
    'jeugd 6 - 14': 'entertainment programs for 6 to 14',
    'educatie': 'informational/educational/school programs',
    'kids 0 - 6': 'pre-school children\'s programs',
    'kids, 0-6': 'pre-school children\'s programs',

    # 06
    'ballet': 'ballet',
    'volksmuziek': 'folk/traditional music',
    'jazz': 'jazz',
    'dans': 'music/ballet/dance',
    'easy listening': 'music/ballet/dance',
    'muziek': 'music/ballet/dance',
    'musical': 'musical/opera',
    'musical/opera': 'musical/opera',
    'opera': 'musical/opera',
    'rock/pop': 'rock/pop',
    'klassiek': 'serious music/classical music',

    # 07
    'kunst magazine': 'arts magazines/culture magazines',
    'kunst/cultuur': 'arts magazines/culture magazines',
    'kunstnijverheid': 'arts magazines/culture magazines',
    'lifestyle': 'arts/culture (without music)',
    'special': 'broadcasting/press',
    'shorts': 'experimental film/video',
    'mode': 'fashion',
    #'': 'film/cinema',   # prevent any mapping to this as it will result in movies being treated as tvshows.
    #'': 'fine arts',
    'literatuur': 'literature',
    #'': 'new media',
    'beeldende kunst': 'performing arts',
    'podiumkunsten': 'performing arts',
    'popart': 'popular culture/traditional arts',
    'religie': 'religion',

    # 08
    'business & financial': 'economics/social advisory',
    'economie': 'economics/social advisory',
    'misdaad': 'economics/social advisory',
    'recht': 'economics/social advisory',
    'actualiteiten': 'magazines/reports/documentary',
    'cheerleading': 'magazines/reports/documentary',
    'opvoeden': 'magazines/reports/documentary',
    'beroemdheden': 'remarkable people',
    'biografie': 'remarkable people',
    'consumentenprogramma\'s': 'social/political issues/economics',
    'goede doelen': 'social/political issues/economics',
    'lhbti': 'social/political issues/economics',
    'maatschappelijk': 'social/political issues/economics',
    'militair': 'social/political issues/economics',
    'oorlog': 'social/political issues/economics',
    'paranormaal': 'social/political issues/economics',
    'politiek': 'social/political issues/economics',
    'reality': 'social/political issues/economics',
    'veiling': 'social/political issues/economics',
    'zelfhulp': 'social/political issues/economics',

    # 09
    #'': 'education/science/factual topics',
    'expedities': 'foreign countries/expeditions',
    'educatie divers': 'further education',
    'talen': 'languages',
    'geneeskunde': 'medicine/physiology/psychology',
    'medisch': 'medicine/physiology/psychology',
    'dieren': 'nature/animals/environment',
    'hondenshows': 'nature/animals/environment',
    'natuur en milieu': 'nature/animals/environment',
    'natuur': 'nature/animals/environment',
    'samenleving': 'social/spiritual sciences',
    'sociologie': 'social/spiritual sciences',
    'computers': 'technology/natural sciences',
    'technologie': 'technology/natural sciences',
    'wetenschap': 'technology/natural sciences',

    # 10
    'shoppen': 'advertisement/shopping',
    'culinair': 'cooking',
    'koken': 'cooking',
    'exercise': 'fitness and health',
    'fit en gezond': 'fitness and health',
    'gezondheid': 'fitness and health',
    'home & garden': 'gardening',
    'tuinieren': 'gardening',
    'bouwen en verbouwen': 'handicraft',
    'doe-het-zelf': 'handicraft',
    'klussen': 'handicraft',
    'auto\'s': 'leisure hobbies',
    'landbouw': 'leisure hobbies',
    'outdoor': 'leisure hobbies',
    'vakantie': 'leisure hobbies',
    'verzamelen': 'leisure hobbies',
    'vissen': 'leisure hobbies',
    'vrije tijd': 'leisure hobbies',
    'auto en motor': 'motoring',
    'reizen': 'tourism/travel'
  }

  def __init__(self):
    impl = xml.dom.minidom.getDOMImplementation()
    doctype = impl.createDocumentType('tv', None, 'https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.dtd')
    self.document = impl.createDocument(None, 'tv', doctype)
    self.document.documentElement.setAttribute('source-info-url', 'https://horizon.tv')
    self.document.documentElement.setAttribute('source-info-name', 'Ziggo Go/Horizon API')
    self.document.documentElement.setAttribute('generator-info-name', 'HorEPG v1.0')
    self.document.documentElement.setAttribute('generator-info-url', 'beralt.nl/horepg')

  def addChannel(self, channel_id, suggested_names, icon=None):
    element = self.document.createElement('channel')
    element.setAttribute('id', sanitize_channel_id(channel_id))

    for display_name in suggested_names:
      if display_name in XMLTVDocument.replace_display_name and len(XMLTVDocument.replace_display_name[display_name]) > 0:
        for renamed_display_name in XMLTVDocument.replace_display_name[display_name]:
          self.addDisplayName(element, renamed_display_name)
      else:
        self.addDisplayName(element, display_name)

    if (icon):
      lu_element = self.document.createElement('icon')
      lu_element.setAttribute('src', icon)
      element.appendChild(lu_element)

    self.document.documentElement.appendChild(element)

  def addDisplayName(self, channel_element, display_name):
    dn_element = self.document.createElement('display-name')
    dn_text = self.document.createTextNode(display_name)
    dn_element.appendChild(dn_text)
    channel_element.appendChild(dn_element)

  def addProgramme(self, channel_id, title, start, end, cast=list(), categories=list(), copyright_year=None, description=None, directors=list(), episode=None, images=list(), language=None, medium="TV", secondary_title=None, subtitles=list(), sign_languages=list(), parental_rating=list()):
    element = self.document.createElement('programme')
    element.setAttribute('start', XMLTVDocument.convert_time(int(start)))
    element.setAttribute('stop', XMLTVDocument.convert_time(int(end)))
    element.setAttribute('channel', sanitize_channel_id(channel_id))
    # quick tags
    self.quick_tag(element, 'title', title)

    if secondary_title:
      self.quick_tag(element, 'sub-title', secondary_title)

    if description:
      self.quick_tag(element, 'desc', description)

    if len(cast) > 0 or len(directors) > 0:
      credits_element = self.document.createElement('credits')
      unique_cast = set()

      for director in directors:
        self.quick_tag(credits_element, 'director', director)
      for actor in cast:
        # prevent duplicate actors
        if actor not in unique_cast:
          unique_cast.add(actor)
          self.quick_tag(credits_element, 'actor', actor)

      element.appendChild(credits_element)

    if copyright_year and len(copyright_year) == 4 and copyright_year.isdecimal():
      self.quick_tag(element, 'date', copyright_year)

    unique_categories = set()
    for cat in categories:
      cat_title = XMLTVDocument.map_category(cat.lower())

      # stop processing if the current programme already has the current category.
      if cat.lower() in unique_categories or cat_title in unique_categories:
        # debug("CHANNEL '{}', PROGRAM '{}': Skipping duplicate category '{}'".format(channel_id, title, cat))
        continue
      # if cat contains no "/" and has no mapping (None != falsey), add cat as custom category.
      elif '/' not in cat and cat_title is None:
        info("CHANNEL '{}', PROGRAM '{}': No XMLTV translation for category '{}'.".format(channel_id, title, cat))
        unique_categories.add(cat.lower())
        self.quick_tag(element, 'category', cat.lower(), { 'lang': 'nl' })
      # add cat_title as category if it was mapped.
      elif cat_title:
        # if the program's category is part of the ETSI "movie/drama" genre, the Horizon medium type is "Movie" and does not have any "episode" information.
        if XMLTVDocument.is_movie_genre(cat_title) and medium == "Movie" and not episode:
          # add additional "movie" category if it has not been added yet. Tvheadend needs it to properly classify a recording as movie. See: https://github.com/tvheadend/tvheadend/blob/3d19cd20e87350db7e0d1dd6bd382ec9ee2853b3/src/dvr/dvr_rec.c#L497
          if "movie" not in unique_categories:
            unique_categories.add("movie")
            self.quick_tag(element, 'category', "movie", { 'lang': 'en' })
          unique_categories.add(cat_title)
          self.quick_tag(element, 'category', cat_title, { 'lang': 'en' })
        # if the program's category is NOT part of the ETSI "movie/drama" genre and the Horizon medium type is "TV".
        elif not XMLTVDocument.is_movie_genre(cat_title) and medium == "TV":
          unique_categories.add(cat_title)
          self.quick_tag(element, 'category', cat_title, { 'lang': 'en' })
        #else:
          # debug("CHANNEL '{}', PROGRAM '{}': Skipping ambiguous category mapping for '{}' programme with category '{}'".format(channel_id, title, medium, cat))
      else:
        debug("CHANNEL '{}', PROGRAM '{}': Skipping category '{}' due to '/' or empty string mapping.".format(channel_id, title, cat))

    if language:
      self.quick_tag(element, 'language', language)

    for image in images:
      self.quick_tag(element, 'icon', None, { 'src': image })

    if episode:
      self.quick_tag(element, 'episode-num', episode, {'system': 'xmltv_ns'})

    if len(subtitles) > 0:
      for subtitle in subtitles:
        subtitles_element = self.document.createElement('subtitles')
        subtitles_element.setAttribute('type', 'onscreen')
        self.quick_tag(subtitles_element, 'language', subtitle)
        element.appendChild(subtitles_element)

    if len(sign_languages) > 0:
      for sign_language in sign_languages:
        sign_language_element = self.document.createElement('subtitles')
        sign_language_element.setAttribute('type', 'deaf-signed')
        self.quick_tag(sign_language_element, 'language', sign_language)
        element.appendChild(sign_language_element)

    if parental_rating:
      parental_rating_element = self.document.createElement('rating')
      parental_rating_element.setAttribute('system', 'Kijkwijzer')
      self.quick_tag(parental_rating_element, 'value', parental_rating)
      element.appendChild(parental_rating_element)

    self.document.documentElement.appendChild(element)

  def is_movie_genre(category_title):
    return (category_title == 'adult movie/drama'
      or category_title == 'adventure/western/war'
      or category_title == 'comedy'
      or category_title == 'detective/thriller'
      or category_title == 'movie/drama'
      or category_title == 'romance'
      or category_title == 'science fiction/fantasy/horror'
      or category_title == 'serious/classical/religious/historical movie/drama'
      or category_title == 'soap/melodrama/folkloric')

  def map_category(cat):
    if cat in XMLTVDocument.category_map:
      return XMLTVDocument.category_map[cat]
    return None

  def quick_tag(self, parent, tag, content=None, attributes=False):
    element = self.document.createElement(tag)
    if content:
      text = self.document.createTextNode(content)
      element.appendChild(text)
    if attributes:
      for k, v in attributes.items():
        element.setAttribute(k, v)
    parent.appendChild(element)

  def set_date(self, unix_time):
    if isinstance(unix_time, int):
      self.document.documentElement.setAttribute('date', XMLTVDocument.convert_time(unix_time/1000))

  def convert_time(t):
    return time.strftime('%Y%m%d%H%M%S', time.gmtime(t))
