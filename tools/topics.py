"""Keyword-based GK topic classifier for SSC GD PART-B questions.

Classifies a question (stem + options text, English or Hindi) into one of the
standard GK topics. Falls back to 'Static GK' when nothing matches.
"""
import re

# Ordered list: first matching topic wins (more specific topics first).
TOPIC_KEYWORDS = [
    ("Polity & Constitution", [
        # english
        "constitution", "article", "amendment", "parliament", "lok sabha",
        "rajya sabha", "president", "prime minister", "governor", "supreme court",
        "high court", "fundamental right", "directive principle", "preamble",
        "election commission", "finance commission", "niti aayog", "cabinet",
        "judiciary", "legislature", "ordinance", "schedule", "panchayat",
        "attorney general", "chief minister", "vidhan sabha", "bill", "veto",
        # hindi
        "संविधान", "अनुच्छेद", "संशोधन", "संसद", "लोकसभा", "राज्यसभा",
        "राष्ट्रपति", "प्रधानमंत्री", "राज्यपाल", "सर्वोच्च न्यायालय",
        "उच्च न्यायालय", "मौलिक अधिकार", "नीति निदेशक", "प्रस्तावना",
        "निर्वाचन आयोग", "वित्त आयोग", "मंत्रिपरिषद", "न्यायपालिका",
        "विधायिका", "अध्यादेश", "अनुसूची", "पंचायत", "मुख्यमंत्री",
        "विधानसभा", "विधेयक",
    ]),
    ("Geography", [
        "river", "mountain", "plateau", "climate", "monsoon", "soil", "lake",
        "desert", "ocean", "latitude", "longitude", "tropic", "forest",
        "crop", "mineral", "delta", "peninsula", "himalaya", "valley",
        "rainfall", "biosphere", "national park", "wildlife sanctuary",
        "नदी", "पर्वत", "पठार", "जलवायु", "मानसून", "मृदा", "मिट्टी", "झील",
        "रेगिस्तान", "महासागर", "अक्षांश", "देशांतर", "वन", "फसल", "खनिज",
        "हिमालय", "घाटी", "वर्षा", "मैदान", "जैवमंडल", "उद्यान", "पठार",
        "अभयारण्य", "भौतिक", "जलप्रपात",
    ]),
    ("History", [
        "dynasty", "empire", "emperor", "mughal", "maurya", "gupta", "sultanate",
        "freedom", "revolt", "movement", "independence", "ancient", "medieval",
        "battle", "treaty", "civilization", "harappa", "indus", "veda", "vedic",
        "buddha", "ashoka", "akbar", "shivaji", "gandhi", "congress",
        "राजवंश", "साम्राज्य", "सम्राट", "मुगल", "मौर्य", "गुप्त", "सल्तनत",
        "स्वतंत्रता", "विद्रोह", "आंदोलन", "प्राचीन", "मध्यकाल", "युद्ध",
        "संधि", "सभ्यता", "हड़प्पा", "सिंधु", "वेद", "वैदिक", "बुद्ध",
        "अशोक", "अकबर", "शिवाजी", "गांधी", "कांग्रेस",
    ]),
    ("Economy", [
        "gdp", "inflation", "tax", "budget", "rbi", "repo", "fiscal", "monetary",
        "bank", "stock", "subsidy", "poverty", "trade", "export", "import",
        "ease of doing business", "sensex", "nifty", "currency", "rupee",
        "जीडीपी", "मुद्रास्फीति", "कर", "बजट", "रिजर्व बैंक", "रेपो",
        "राजकोषीय", "मौद्रिक", "बैंक", "सब्सिडी", "गरीबी", "व्यापार",
        "निर्यात", "आयात", "मुद्रा", "रुपया", "सूचकांक",
    ]),
    ("Science & Technology", [
        "acceleration", "velocity", "force", "gravity", "energy", "atom",
        "molecule", "cell", "enzyme", "acid", "reaction", "electron", "current",
        "magnetic", "light", "sound", "reflex", "vitamin", "blood", "digestion",
        "isro", "satellite", "rocket", "dna", "chromosome", "photosynthesis",
        "newton", "chemical", "physics", "biology", "disease", "vaccine",
        "त्वरण", "वेग", "बल", "गुरुत्वाकर्षण", "ऊर्जा", "परमाणु", "अणु",
        "कोशिका", "एंजाइम", "अम्ल", "अभिक्रिया", "इलेक्ट्रॉन", "विद्युत",
        "चुंबकीय", "प्रकाश", "ध्वनि", "विटामिन", "रक्त", "पाचन", "उपग्रह",
        "रॉकेट", "गुणसूत्र", "प्रकाश संश्लेषण", "रासायनिक", "रोग", "टीका",
        "चुंबकीय क्षेत्र", "घर्षण",
    ]),
    ("Sports", [
        "olympic", "cricket", "football", "hockey", "tennis", "medal",
        "trophy", "cup", "championship", "tournament", "athlete", "kabaddi",
        "badminton", "wrestling", "fifa", "world cup", "commonwealth",
        "ओलंपिक", "क्रिकेट", "फुटबॉल", "हॉकी", "टेनिस", "पदक", "ट्रॉफी",
        "कप", "चैंपियनशिप", "टूर्नामेंट", "खिलाड़ी", "कबड्डी", "बैडमिंटन",
        "कुश्ती", "विश्व कप",
    ]),
    ("Art & Culture", [
        "dance", "festival", "music", "raga", "instrument", "painting",
        "classical", "folk", "temple", "architecture", "scripture", "ritual",
        "tradition", "guru granth", "veda", "gita", "tabla", "sitar",
        "नृत्य", "त्योहार", "संगीत", "राग", "वाद्ययंत्र", "वाद्य", "चित्रकला",
        "शास्त्रीय", "लोक", "मंदिर", "वास्तुकला", "ग्रंथ", "अनुष्ठान",
        "परंपरा", "तबला", "सितार", "गायन", "महोत्सव",
    ]),
    ("Books & Authors", [
        "author", "book", "novel", "written by", "wrote", "poet", "writer",
        "autobiography", "sequel",
        "लेखक", "पुस्तक", "उपन्यास", "लिखा", "कवि", "लेखिका", "आत्मकथा",
        "सीक्वल", "रचना", "किताब",
    ]),
    ("Awards & Honours", [
        "award", "prize", "honour", "nobel", "bharat ratna", "padma",
        "gallantry", "oscar", "recipient", "felicitated",
        "पुरस्कार", "सम्मान", "नोबेल", "भारत रत्न", "पद्म", "वीरता",
        "प्राप्तकर्ता",
    ]),
    ("Schemes & Government", [
        "scheme", "yojana", "mission", "abhiyan", "campaign", "policy",
        "programme", "pm-", "pradhan mantri", "ministry",
        "योजना", "मिशन", "अभियान", "नीति", "कार्यक्रम", "प्रधानमंत्री",
        "मंत्रालय", "सरकार",
    ]),
    ("Current Affairs", [
        "2024", "2025", "in news", "recently", "summit", "appointed",
        "launched", "hosted", "signed", "inaugurated",
        "समाचार", "हाल ही", "शिखर सम्मेलन", "नियुक्त", "लॉन्च", "मेजबानी",
        "हस्ताक्षर", "उद्घाटन",
    ]),
]


def classify(stem, options):
    text = (stem or "") + " " + " ".join(options or [])
    low = text.lower()
    for topic, kws in TOPIC_KEYWORDS:
        for kw in kws:
            k = kw.lower()
            # word-ish boundary for short ascii keywords
            if re.search(r'[a-z]', k) and len(k) <= 4:
                if re.search(r'\b' + re.escape(k) + r'\b', low):
                    return topic
            elif k in low:
                return topic
    return "Static GK"


if __name__ == '__main__':
    import json
    from collections import Counter
    recs = json.load(open('Gd/data/ocr_cache.json'))
    cnt = Counter()
    for r in recs:
        cnt[classify(r['stem'], r['options'])] += 1
    for t, c in cnt.most_common():
        print(f'{c:4d}  {t}')
    print('total', sum(cnt.values()))
