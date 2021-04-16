import xml.dom.minidom
import time
import logging
import re

def debug(msg):
  logging.debug(msg)

def sanitize_channel_id(channel_id):
  # To pass XMLTV validation, the primary goal is to adhere to the xmltv.dtd (https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.dtd).
  # But XMLTV often (e.g. tv_validate_file) performs additional validation against a more strict Perl ValidateFile.pm file (https://raw.githubusercontent.com/XMLTV/xmltv/master/lib/ValidateFile.pm).
  # The "channel id" definition in the DTD is comfortably loose although they suggest the RFC2838 format (https://tools.ietf.org/html/rfc2838).
  # The "channel id" definition of ValidateFile.pm enforces a format according to this regex /^[-a-zA-Z0-9]+(\.[-a-zA-Z0-9]+)+$/ which does not match a RFC2838 format.
  # Both validations do seem to approve the regex format, so let's stick to that.
  channel_id_spec = re.compile('^[-a-zA-Z0-9]+(\.[-a-zA-Z0-9]+)+$')
  sanitized_channel_name = channel_id.replace('_', '-').replace(':', '.')
  return sanitized_channel_name if re.match(channel_id_spec, sanitized_channel_name) else channel_id

def warning(msg):
  logging.warning(msg)


class XMLTVDocument(object):
  # this renames some of the channels
  replace_display_name = {
    #'sample channel name HD': [ 'sample channel name', 'some other name' ]
  }
  
  # Target names taken from: https://github.com/tvheadend/tvheadend/blob/master/src/epg.c
  # All entries must be lower case
  category_map = {
    # 00
    'onbepaald': '',
    'miniseries': '',  # Format, not content
    'event': '',  # Used for various categories

    # 01
    'tv drama': 'movie/drama',
    'actie': 'movie/drama',
    'familie': 'movie/drama',
    'dramaseries': 'movie/drama',
    'thriller': 'detective/thriller',
    'detective': 'detective/thriller',
    'mysterie': 'detective/thriller',
    'misdaaddrama': 'detective/thriller',
    'avontuur': 'adventure/western/war',
    'western': 'adventure/western/war',
    'horror': 'science fiction/fantasy/horror',
    'sci-fi': 'science fiction/fantasy/horror',
    'sci-fi/horror': 'science fiction/fantasy/horror',
    'sciencefiction': 'science fiction/fantasy/horror',
    'fantasy': 'science fiction/fantasy/horror',
    'komedie': 'comedy',
    'sitcoms': 'comedy',
    'zwarte komedie': 'comedy',
    'standup komedie': 'comedy',
    'melodrama': 'soap/melodrama/folkloric',
    'soap': 'soap/melodrama/folkloric',
    'romantiek': 'romance',
    'romantisch': 'romance',
    'romantische komedie': 'romance',
    'drama': 'serious/classical/religious/historical movie/drama',
    'historisch drama': 'serious/classical/religious/historical movie/drama',
    'erotiek': 'adult movie/drama',
    'erotisch': 'adult movie/drama',

    # 02
    'nieuws': 'news/current affairs',
    'actualiteit': 'news/current affairs',
    'actualiteitenprogramma\'s': 'news/current affairs',
    'weer': 'news/weather report',
    'nieuws documentaire': 'news magazine',
    'documentaire': 'documentary',
    'historisch': 'documentary',
    'geschiedenis': 'documentary',
    'waar gebeurd': 'documentary',
    'docudrama': 'documentary',
    'docusoap': 'documentary',
    'discussie': 'discussion/interview/debate',
    'interview': 'discussion/interview/debate',
    'debat': 'discussion/interview/debate',

    # 03
    'show': 'show/game show',
    'entertainment': 'show/game show',
    'spelshow': 'show/game show',
    'variété': 'variety show',
    'variete': 'variety show',
    'theater': 'variety show',
    'bloemlezing': 'variety show',
    'talkshow': 'talk show',
    'talk show': 'talk show',

    # 04
    'sport': 'sports',
    'extreme sporten': 'sports',
    'snooker': 'sports',
    'tennis': 'sports',
    'golf': 'sports',
    'snowboarden': 'sports',
    'skiën': 'sports',
    'freestyle skiën': 'sports',
    'alpineskiën': 'sports',
    'skispringen': 'sports',
    'vliegsport': 'sports',
    'triathlon': 'sports',
    'biathlon': 'sports',
    'schermen': 'sports',
    'curling': 'sports',
    'ijshockey': 'sports',
    'kunstschaatsen': 'sports',
    'gewichtheffen': 'sports',
    'boksen': 'sports',
    'stierenvechten': 'sports',
    'esports': 'sports',
    'gamen': 'sports',
    'evenementen': 'special events (olympic games, world cup, etc.)',
    'olympische spelen': 'special events (olympic games, world cup, etc.)',
    'sportmagazine': 'sports magazines',
    'sporttalkshow': 'sports magazines',
    'voetbal': 'football/soccer',
    'american football': 'football/soccer',
    'tennis/squash': 'tennis/squash',
    'teamsporten': 'team sports (excluding football)',
    'hockey': 'team sports (excluding football)',
    'basketbal': 'team sports (excluding football)',
    'rugby': 'team sports (excluding football)',
    'rugby league': 'team sports (excluding football)',
    'wielrennen': 'team sports (excluding football)',
    'atletiek': 'athletics',
    'turnen': 'athletics',
    'motorsport': 'motor sport',
    'extreme': 'motor sport',
    'motors': 'motor sport',
    'motorracen': 'motor sport',
    'watersport': 'water sport',
    'wintersport': 'winter sports',
    'paardensport': 'equestrian',
    'gevechtssport': 'martial sports',
    'worstelen': 'martial sports',
    'mixed martial arts (mma)': 'martial sports',

    # 05
    'kids/jeugd': 'children\'s / youth programs',
    'kinderen': 'children\'s / youth programs',
    'kids 0 - 6': 'pre-school children\'s programs',
    'kids, 0-6': 'pre-school children\'s programs',
    'jeugd 6 - 14': 'entertainment programs for 6 to 14',
    'jeugd 10 - 16': 'entertainment programs for 10 to 16',
    'educatie': 'information/educational/school program',
    'poppenspel': 'cartoon/puppets',
    'animatie': 'cartoon/puppets',
    'anime': 'cartoon/puppets',

    # 06
    'muziek': 'music/ballet/dance',
    'easy listening': 'music/ballet/dance',
    'dans': 'music/ballet/dance',
    'rock/pop': 'rock/pop',
    'klassiek': 'serious music/classical music',
    'volksmuziek': 'folk/traditional music',
    'jazz': 'jazz',
    'musical': 'musical/opera',
    'musical/opera': 'musical/opera',
    'opera': 'musical/opera',
    'ballet': 'ballet',

    # 07
    'lifestyle': 'arts/culture (without music)',
    'beeldende kunst': 'performing arts',
    'podiumkunsten': 'performing arts',
    'religie': 'religion',
    'popart': 'popular culture/traditional arts',
    'literatuur': 'literature',
    'speelfilm': 'film/cinema',
    'film': 'film/cinema',
    'film/cinema': 'film/cinema',
    'shorts': 'experimental film/video',
    'special': 'broadcasting/press',
    'kunst magazine': 'arts magazines/culture magazines',
    'kunst/cultuur': 'arts magazines/culture magazines',
    'kunstnijverheid': 'arts magazines/culture magazines',
    'mode': 'fashion',

    # 08
    'maatschappelijk': 'social/political issues/economics',
    'consumentenprogramma\'s': 'social/political issues/economics',
    'reality': 'social/political issues/economics',
    'politiek': 'social/political issues/economics',
    'oorlog': 'social/political issues/economics',
    'militair': 'social/political issues/economics',
    'zelfhulp': 'social/political issues/economics',
    'veiling': 'social/political issues/economics',
    'paranormaal': 'social/political issues/economics',
    'lhbti': 'social/political issues/economics',
    'actualiteiten': 'magazines/reports/documentary',
    'cheerleading': 'magazines/reports/documentary',
    'opvoeden': 'magazines/reports/documentary',
    'economie': 'economics/social advisory',
    'business & financial': 'economics/social advisory',
    'recht': 'economics/social advisory',
    'misdaad': 'economics/social advisory',
    'beroemdheden': 'remarkable people',
    'biografie': 'remarkable people',

    # 09
    'natuur': 'nature/animals/environment',
    'natuur en milieu': 'nature/animals/environment',
    'dieren': 'nature/animals/environment',
    'technologie': 'technology/natural sciences',
    'wetenschap': 'technology/natural sciences',
    'computers': 'technology/natural sciences',
    'geneeskunde': 'medicine/physiology/psychology',
    'medisch': 'medicine/physiology/psychology',
    'expedities': 'foreign countries/expeditions',
    'sociologie': 'social/spiritual sciences',
    'samenleving': 'social/spiritual sciences',
    'educatie divers': 'further education',
    'talen': 'languages',

    # 10
    'vrije tijd': 'leisure hobbies',
    'vakantie': 'leisure hobbies',
    'outdoor': 'leisure hobbies',
    'auto\'s': 'leisure hobbies',
    'vissen': 'leisure hobbies',
    'verzamelen': 'leisure hobbies',
    'landbouw': 'leisure hobbies',
    'reizen': 'tourism / travel',
    'klussen': 'handicraft',
    'doe-het-zelf': 'handicraft',
    'bouwen en verbouwen': 'handicraft',
    'auto en motor': 'motoring',
    'gezondheid': 'fitness and health',
    'exercise': 'fitness and health',
    'fit en gezond': 'fitness and health',
    'koken': 'cooking',
    'culinair': 'cooking',
    'shoppen': 'advertisement / shopping',
    'tuinieren': 'gardening',
    'home & garden': 'gardening',
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

  def addProgramme(self, channel_id, title, start, end, episode=None, secondary_title=None, description=None,
                   categories=None):
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

    unique_categories = set()
    if categories:
      for cat in categories:
        cat_title = XMLTVDocument.map_category(cat.lower())
        if cat.lower() in unique_categories or cat_title in unique_categories:
          debug("CHANNEL '{}', PROGRAM '{}': Skipping duplicate category '{}'".format(channel_id, title, cat))
        elif '/' not in cat and cat_title is None:
          warning("CHANNEL '{}', PROGRAM '{}': No XMLTV translation for category '{}'".format(channel_id, title, cat))
          unique_categories.add(cat.lower())
          self.quick_tag(element, 'category', cat.lower())
        elif cat_title:
          unique_categories.add(cat_title)
          self.quick_tag(element, 'category', cat_title)
        else:
          debug("CHANNEL '{}', PROGRAM '{}': Skipping category '{}' due to '/' or empty string mapping".format(channel_id, title, cat))

    if episode:
      self.quick_tag(element, 'episode-num', episode, {'system': 'xmltv_ns'})
    
    self.document.documentElement.appendChild(element)

  def map_category(cat):
    if cat in XMLTVDocument.category_map:
      return XMLTVDocument.category_map[cat]
    return None

  def quick_tag(self, parent, tag, content, attributes=False):
    element = self.document.createElement(tag)
    text = self.document.createTextNode(content)
    element.appendChild(text)
    if attributes:
      for k, v in attributes.items():
        element.setAttribute(k, v)
    parent.appendChild(element)

  def convert_time(t):
    return time.strftime('%Y%m%d%H%M%S', time.gmtime(t))
