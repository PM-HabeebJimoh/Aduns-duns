"""Multilingual need-cue lexicon.

Lets the engine read local platforms *in their own language* instead of only English.
Each language has:
  cues[need_type]  – phrases people use when a need is unmet / unaffordable / scarce / normalized / inefficient
  search           – short phrases for searching social/news platforms (most productive cues)
  suggest          – autocomplete templates ("{x}" placeholder optional) revealing latent demand

Matching is substring-based on lowercased text, so it works for scripts without spaces (zh, ja, th).
"""
from __future__ import annotations

L: dict[str, dict] = {
    "en": {
        "cues": {
            "unmet": ["can't find", "cannot find", "couldn't find", "no one sells", "nobody sells", "not available",
                      "hard to find", "impossible to get", "no supplier", "where can i get", "where can i buy",
                      "is there any", "wish there was", "looking for a supplier", "no service"],
            "unaffordable": ["too expensive", "can't afford", "cannot afford", "overpriced", "price hike", "prices doubled",
                             "so expensive", "unaffordable", "cost of living"],
            "scarcity": ["shortage", "scarcity", "out of stock", "sold out", "rationing", "no fuel", "no water",
                         "no electricity", "no power", "blackout", "queue for"],
            "normalized": ["always takes", "only available abroad", "have to travel to", "have to import", "waiting list",
                           "waited for months", "that's just how it is", "we just live with", "every year we lose"],
            "inefficient": ["keeps breaking", "no spare parts", "nobody can fix", "no technician", "broke down again",
                            "manually", "workaround"],
        },
        "search": ["shortage", "can't find", "too expensive", "no one sells", "waiting list", "no spare parts",
                   "no water", "no electricity", "price hike", "out of stock"],
        "suggest": ["where to buy", "where can i get", "why is {x} so expensive", "how to get", "shortage of",
                    "no {x} in", "price of"],
    },
    "fr": {
        "cues": {
            "unmet": ["introuvable", "impossible de trouver", "on ne trouve pas", "pas disponible", "aucun fournisseur",
                      "personne ne vend", "où acheter", "où trouver"],
            "unaffordable": ["trop cher", "hors de prix", "flambée des prix", "hausse des prix", "vie chère",
                             "pas les moyens"],
            "scarcity": ["pénurie", "rupture de stock", "manque de", "coupure d'électricité", "délestage",
                         "pas d'eau", "rationnement", "files d'attente"],
            "normalized": ["il faut aller à", "seulement à l'étranger", "liste d'attente", "on attend des mois",
                           "c'est comme ça", "chaque année on perd"],
            "inefficient": ["pas de pièces de rechange", "personne ne sait réparer", "toujours en panne", "encore en panne"],
        },
        "search": ["pénurie", "rupture de stock", "trop cher", "introuvable", "délestage", "manque de", "flambée des prix"],
        "suggest": ["où acheter", "où trouver", "prix de", "pourquoi {x} est cher", "pénurie de"],
    },
    "es": {
        "cues": {
            "unmet": ["no encuentro", "no se consigue", "imposible conseguir", "no hay proveedor", "nadie vende",
                      "dónde comprar", "dónde conseguir", "no está disponible"],
            "unaffordable": ["muy caro", "demasiado caro", "no alcanza", "subida de precios", "aumento de precios",
                             "carísimo", "no me alcanza"],
            "scarcity": ["escasez", "desabastecimiento", "agotado", "falta de", "sin agua", "sin luz", "apagón",
                         "racionamiento", "colas para"],
            "normalized": ["siempre tarda", "solo en el extranjero", "hay que viajar a", "lista de espera",
                           "meses esperando", "así es aquí", "todos los años perdemos"],
            "inefficient": ["no hay repuestos", "nadie lo arregla", "se descompone siempre", "otra vez dañado"],
        },
        "search": ["escasez", "desabastecimiento", "no se consigue", "muy caro", "sin agua", "apagón", "falta de"],
        "suggest": ["dónde comprar", "dónde conseguir", "precio de", "por qué {x} es tan caro", "escasez de"],
    },
    "pt": {
        "cues": {
            "unmet": ["não encontro", "não acho", "impossível encontrar", "ninguém vende", "onde comprar",
                      "onde encontrar", "não está disponível", "sem fornecedor"],
            "unaffordable": ["muito caro", "caro demais", "aumento de preço", "preços subiram", "não dá para pagar"],
            "scarcity": ["falta de", "escassez", "desabastecimento", "esgotado", "sem água", "sem luz", "apagão",
                         "racionamento", "filas para"],
            "normalized": ["sempre demora", "só no exterior", "tem que viajar", "lista de espera", "meses esperando",
                           "é assim mesmo", "todo ano perdemos"],
            "inefficient": ["sem peças", "ninguém conserta", "sempre quebra", "quebrou de novo"],
        },
        "search": ["falta de", "escassez", "muito caro", "sem água", "sem luz", "desabastecimento", "não encontro"],
        "suggest": ["onde comprar", "onde encontrar", "preço do", "por que {x} está caro", "falta de"],
    },
    "ar": {
        "cues": {
            "unmet": ["لا يوجد", "لا أجد", "غير متوفر", "صعب الحصول", "أين أشتري", "أين أجد", "لا أحد يبيع"],
            "unaffordable": ["غالي جدا", "ارتفاع الأسعار", "غلاء", "لا أستطيع تحمل", "الأسعار نار"],
            "scarcity": ["نقص", "أزمة", "شح", "انقطاع الكهرباء", "انقطاع المياه", "طوابير", "نفاد"],
            "normalized": ["دائما يستغرق", "فقط في الخارج", "قائمة انتظار", "ننتظر أشهر", "هكذا الحال"],
            "inefficient": ["لا توجد قطع غيار", "لا أحد يصلح", "معطل دائما"],
        },
        "search": ["نقص", "أزمة", "غلاء", "انقطاع الكهرباء", "انقطاع المياه", "غير متوفر"],
        "suggest": ["أين أشتري", "سعر", "أين أجد", "لماذا {x} غالي"],
    },
    "ru": {
        "cues": {
            "unmet": ["не могу найти", "негде купить", "нигде нет", "не продают", "где купить", "где найти", "нет в наличии"],
            "unaffordable": ["слишком дорого", "очень дорого", "цены выросли", "подорожание", "не по карману"],
            "scarcity": ["дефицит", "нехватка", "отключение света", "нет воды", "очереди", "закончился"],
            "normalized": ["всегда приходится", "только за границей", "очередь на", "ждать месяцами", "так у нас всегда"],
            "inefficient": ["нет запчастей", "некому починить", "постоянно ломается"],
        },
        "search": ["дефицит", "нехватка", "подорожание", "нет в наличии", "негде купить"],
        "suggest": ["где купить", "где найти", "цена на", "почему {x} так дорого"],
    },
    "uk": {
        "cues": {
            "unmet": ["не можу знайти", "ніде немає", "де купити", "немає в наявності"],
            "unaffordable": ["дуже дорого", "подорожчання", "ціни зросли"],
            "scarcity": ["дефіцит", "нестача", "відключення світла", "немає води", "черги"],
            "normalized": ["тільки за кордоном", "чекати місяцями", "черга на"],
            "inefficient": ["немає запчастин", "постійно ламається"],
        },
        "search": ["дефіцит", "подорожчання", "відключення світла", "нестача"],
        "suggest": ["де купити", "ціна на"],
    },
    "zh": {
        "cues": {
            "unmet": ["买不到", "找不到", "哪里买", "没有卖", "缺货", "无货"],
            "unaffordable": ["太贵", "涨价", "买不起", "价格上涨"],
            "scarcity": ["短缺", "紧缺", "停电", "停水", "排队", "断货"],
            "normalized": ["只能去国外", "要等几个月", "一直这样", "排长队"],
            "inefficient": ["没有配件", "没人会修", "经常坏"],
        },
        "search": ["短缺", "买不到", "太贵", "涨价", "停电", "缺货"],
        "suggest": ["哪里买", "价格", "为什么{x}这么贵"],
    },
    "ja": {
        "cues": {
            "unmet": ["見つからない", "売ってない", "手に入らない", "どこで買える", "在庫なし"],
            "unaffordable": ["高すぎる", "値上げ", "高騰", "買えない"],
            "scarcity": ["不足", "品薄", "品切れ", "停電", "断水", "行列"],
            "normalized": ["何ヶ月も待つ", "海外でしか", "いつもこう"],
            "inefficient": ["部品がない", "直せる人がいない", "すぐ壊れる"],
        },
        "search": ["不足", "品薄", "値上げ", "手に入らない", "高騰"],
        "suggest": ["どこで買える", "値段", "なぜ高い"],
    },
    "ko": {
        "cues": {
            "unmet": ["구할 수 없", "어디서 사", "품절", "안 팔아", "찾을 수 없"],
            "unaffordable": ["너무 비싸", "가격 인상", "물가 상승", "감당 못"],
            "scarcity": ["부족", "품귀", "정전", "단수", "대란"],
            "normalized": ["몇 달 기다려", "해외에서만", "원래 그래"],
            "inefficient": ["부품이 없", "고칠 사람이 없", "자주 고장"],
        },
        "search": ["부족", "품귀", "품절", "가격 인상", "대란"],
        "suggest": ["어디서 사", "가격"],
    },
    "hi": {
        "cues": {
            "unmet": ["नहीं मिल रहा", "कहाँ मिलेगा", "कहीं नहीं मिलता", "उपलब्ध नहीं"],
            "unaffordable": ["बहुत महंगा", "महंगाई", "दाम बढ़", "कीमत बढ़"],
            "scarcity": ["कमी", "किल्लत", "बिजली कटौती", "पानी नहीं", "लंबी कतार", "संकट"],
            "normalized": ["हमेशा ऐसा", "बाहर जाना पड़ता", "महीनों इंतजार"],
            "inefficient": ["पार्ट्स नहीं", "कोई ठीक नहीं करता", "बार बार खराब"],
        },
        "search": ["किल्लत", "कमी", "महंगाई", "बिजली कटौती", "पानी संकट"],
        "suggest": ["कहाँ मिलेगा", "कीमत", "कहाँ से खरीदें"],
    },
    "bn": {
        "cues": {
            "unmet": ["পাওয়া যায় না", "কোথায় পাব", "কোথায় কিনব"],
            "unaffordable": ["অনেক দাম", "দাম বেড়েছে", "দাম বৃদ্ধি"],
            "scarcity": ["সংকট", "ঘাটতি", "লোডশেডিং", "পানি নেই"],
            "normalized": ["মাসের পর মাস অপেক্ষা", "বিদেশে যেতে হয়"],
            "inefficient": ["যন্ত্রাংশ নেই", "বারবার নষ্ট"],
        },
        "search": ["সংকট", "দাম বৃদ্ধি", "লোডশেডিং", "ঘাটতি"],
        "suggest": ["কোথায় পাব", "দাম"],
    },
    "ur": {
        "cues": {
            "unmet": ["نہیں ملتا", "کہاں ملے گا", "دستیاب نہیں"],
            "unaffordable": ["بہت مہنگا", "مہنگائی", "قیمتوں میں اضافہ"],
            "scarcity": ["قلت", "بحران", "لوڈشیڈنگ", "پانی نہیں"],
            "normalized": ["مہینوں انتظار", "باہر جانا پڑتا"],
            "inefficient": ["پرزے نہیں", "بار بار خراب"],
        },
        "search": ["قلت", "مہنگائی", "لوڈشیڈنگ", "بحران"],
        "suggest": ["کہاں ملے گا", "قیمت"],
    },
    "id": {
        "cues": {
            "unmet": ["tidak ada yang jual", "susah dicari", "sulit didapat", "beli di mana", "cari di mana", "tidak tersedia"],
            "unaffordable": ["mahal banget", "terlalu mahal", "harga naik", "kenaikan harga", "tidak terjangkau"],
            "scarcity": ["kelangkaan", "langka", "kekurangan", "pemadaman listrik", "mati listrik", "antre", "air mati"],
            "normalized": ["harus ke luar negeri", "menunggu berbulan", "sudah biasa"],
            "inefficient": ["tidak ada suku cadang", "sering rusak", "tidak ada teknisi"],
        },
        "search": ["kelangkaan", "langka", "harga naik", "mati listrik", "susah dicari"],
        "suggest": ["beli di mana", "harga", "cari di mana"],
    },
    "ms": {
        "cues": {
            "unmet": ["tak jumpa", "susah nak cari", "beli di mana", "tiada stok"],
            "unaffordable": ["mahal sangat", "harga naik", "kenaikan harga"],
            "scarcity": ["kekurangan", "bekalan terputus", "gangguan bekalan", "beratur"],
            "normalized": ["kena tunggu berbulan", "dah biasa"],
            "inefficient": ["tiada alat ganti", "selalu rosak"],
        },
        "search": ["kekurangan", "harga naik", "gangguan bekalan", "tiada stok"],
        "suggest": ["beli di mana", "harga"],
    },
    "tl": {
        "cues": {
            "unmet": ["walang mabili", "saan makakabili", "hindi makahanap", "walang stock"],
            "unaffordable": ["sobrang mahal", "pagtaas ng presyo", "taas presyo"],
            "scarcity": ["kakulangan", "brownout", "walang tubig", "walang kuryente", "pila"],
            "normalized": ["matagal talaga", "ganyan talaga"],
            "inefficient": ["walang piyesa", "laging sira"],
        },
        "search": ["kakulangan", "brownout", "walang tubig", "taas presyo"],
        "suggest": ["saan makakabili", "presyo ng"],
    },
    "vi": {
        "cues": {
            "unmet": ["không tìm được", "mua ở đâu", "không có bán", "hết hàng"],
            "unaffordable": ["quá đắt", "tăng giá", "giá cao"],
            "scarcity": ["thiếu hụt", "khan hiếm", "cúp điện", "mất điện", "mất nước", "xếp hàng"],
            "normalized": ["phải ra nước ngoài", "chờ hàng tháng"],
            "inefficient": ["không có phụ tùng", "hay hỏng"],
        },
        "search": ["thiếu hụt", "khan hiếm", "tăng giá", "mất điện", "hết hàng"],
        "suggest": ["mua ở đâu", "giá"],
    },
    "th": {
        "cues": {
            "unmet": ["หาซื้อไม่ได้", "ซื้อที่ไหน", "ไม่มีขาย", "ของหมด"],
            "unaffordable": ["แพงมาก", "ขึ้นราคา", "ราคาแพง"],
            "scarcity": ["ขาดแคลน", "ไฟดับ", "น้ำไม่ไหล", "ต่อคิว"],
            "normalized": ["ต้องไปต่างประเทศ", "รอเป็นเดือน"],
            "inefficient": ["ไม่มีอะไหล่", "เสียบ่อย"],
        },
        "search": ["ขาดแคลน", "ขึ้นราคา", "ไฟดับ", "หาซื้อไม่ได้"],
        "suggest": ["ซื้อที่ไหน", "ราคา"],
    },
    "tr": {
        "cues": {
            "unmet": ["bulamıyorum", "bulunmuyor", "nereden alınır", "satan yok", "stokta yok"],
            "unaffordable": ["çok pahalı", "zam geldi", "fiyatlar arttı", "alamıyoruz"],
            "scarcity": ["kıtlık", "sıkıntısı", "elektrik kesintisi", "su kesintisi", "kuyruk"],
            "normalized": ["aylarca bekliyoruz", "sadece yurt dışında", "hep böyle"],
            "inefficient": ["yedek parça yok", "sürekli bozuluyor", "tamir eden yok"],
        },
        "search": ["kıtlık", "sıkıntısı", "zam", "elektrik kesintisi", "stokta yok"],
        "suggest": ["nereden alınır", "fiyatı", "neden bu kadar pahalı"],
    },
    "fa": {
        "cues": {
            "unmet": ["پیدا نمی‌شود", "کجا بخرم", "نایاب", "موجود نیست"],
            "unaffordable": ["خیلی گران", "گرانی", "افزایش قیمت"],
            "scarcity": ["کمبود", "قطعی برق", "قطعی آب", "صف"],
            "normalized": ["ماه‌ها منتظر", "فقط خارج از کشور"],
            "inefficient": ["قطعه نیست", "مدام خراب"],
        },
        "search": ["کمبود", "گرانی", "قطعی برق", "نایاب"],
        "suggest": ["کجا بخرم", "قیمت"],
    },
    "he": {
        "cues": {"unmet": ["אי אפשר למצוא", "איפה קונים", "אזל"], "unaffordable": ["יקר מדי", "התייקרות", "יוקר המחיה"],
                 "scarcity": ["מחסור", "הפסקת חשמל", "תורים"], "normalized": ["מחכים חודשים"], "inefficient": ["אין חלקי חילוף"]},
        "search": ["מחסור", "התייקרות", "יוקר המחיה"], "suggest": ["איפה קונים", "מחיר"],
    },
    "sw": {
        "cues": {
            "unmet": ["hakuna anayeuza", "sipati", "inapatikana wapi", "haipatikani", "nitapata wapi"],
            "unaffordable": ["ghali sana", "bei imepanda", "kupanda kwa bei", "gharama ya maisha"],
            "scarcity": ["uhaba", "upungufu", "hakuna maji", "umeme umekatika", "kukatika kwa umeme", "foleni"],
            "normalized": ["lazima kusafiri", "tunasubiri miezi", "ndivyo ilivyo"],
            "inefficient": ["hakuna spea", "hakuna fundi", "inaharibika kila mara"],
        },
        "search": ["uhaba", "bei imepanda", "hakuna maji", "kukatika kwa umeme", "upungufu"],
        "suggest": ["nitapata wapi", "bei ya"],
    },
    "ha": {
        "cues": {"unmet": ["ba a samu", "ina zan samu", "babu mai sayarwa"], "unaffordable": ["tsada", "farashi ya tashi", "hauhawar farashi"],
                 "scarcity": ["karancin", "rashin wutar lantarki", "rashin ruwa", "layi"], "normalized": ["haka abin yake"],
                 "inefficient": ["babu kayan gyara"]},
        "search": ["karancin", "tsadar", "hauhawar farashi", "rashin wuta"], "suggest": ["ina zan samu", "farashin"],
    },
    "yo": {
        "cues": {"unmet": ["ko si", "nibo ni mo ti le ri"], "unaffordable": ["o won ju", "owo ti goke"],
                 "scarcity": ["aito", "ko si ina", "ko si omi"], "normalized": [], "inefficient": []},
        "search": ["aito", "owo ti goke"], "suggest": ["nibo ni mo ti le ra"],
    },
    "am": {
        "cues": {"unmet": ["አይገኝም", "የት ይገኛል"], "unaffordable": ["በጣም ውድ", "የዋጋ ጭማሪ", "ኑሮ ውድነት"],
                 "scarcity": ["እጥረት", "የመብራት መቋረጥ", "የውሃ እጥረት", "ሰልፍ"], "normalized": [], "inefficient": []},
        "search": ["እጥረት", "የዋጋ ጭማሪ", "ኑሮ ውድነት"], "suggest": ["የት ይገኛል", "ዋጋ"],
    },
    "so": {
        "cues": {"unmet": ["lama helayo", "xaggee laga helaa"], "unaffordable": ["aad u qaali", "sicir barar"],
                 "scarcity": ["yaraanta", "biyo la'aan", "abaar"], "normalized": [], "inefficient": []},
        "search": ["yaraanta", "sicir barar", "abaar"], "suggest": ["xaggee laga helaa", "qiimaha"],
    },
    "de": {
        "cues": {
            "unmet": ["nicht zu finden", "nirgends erhältlich", "wo kaufen", "nicht lieferbar", "kein anbieter"],
            "unaffordable": ["viel zu teuer", "preiserhöhung", "preise gestiegen", "unbezahlbar"],
            "scarcity": ["mangel", "engpass", "lieferengpass", "knappheit", "ausverkauft", "fachkräftemangel"],
            "normalized": ["monatelang warten", "wartezeit", "wartelisten", "nur im ausland"],
            "inefficient": ["keine ersatzteile", "niemand repariert", "ständig kaputt"],
        },
        "search": ["lieferengpass", "mangel an", "unbezahlbar", "wartezeit", "engpass"],
        "suggest": ["wo kaufen", "preis", "warum ist {x} so teuer"],
    },
    "it": {
        "cues": {
            "unmet": ["introvabile", "non si trova", "dove comprare", "nessuno vende", "non disponibile"],
            "unaffordable": ["troppo caro", "rincari", "aumento dei prezzi", "carissimo"],
            "scarcity": ["carenza", "scarsità", "esaurito", "blackout", "code per"],
            "normalized": ["liste d'attesa", "mesi di attesa", "solo all'estero"],
            "inefficient": ["mancano i ricambi", "nessuno ripara", "sempre rotto"],
        },
        "search": ["carenza", "introvabile", "rincari", "liste d'attesa"],
        "suggest": ["dove comprare", "prezzo", "perché {x} costa così tanto"],
    },
    "nl": {
        "cues": {"unmet": ["niet te vinden", "nergens te koop", "waar kopen"], "unaffordable": ["veel te duur", "prijsstijging", "onbetaalbaar"],
                 "scarcity": ["tekort", "schaarste", "uitverkocht"], "normalized": ["wachtlijst", "maanden wachten"],
                 "inefficient": ["geen onderdelen"]},
        "search": ["tekort", "wachtlijst", "onbetaalbaar", "schaarste"], "suggest": ["waar kopen", "prijs"],
    },
    "pl": {
        "cues": {"unmet": ["nie można znaleźć", "nigdzie nie ma", "gdzie kupić"], "unaffordable": ["za drogo", "podwyżki", "ceny wzrosły"],
                 "scarcity": ["brak", "niedobór", "deficyt", "kolejki"], "normalized": ["miesiące czekania", "kolejka do lekarza"],
                 "inefficient": ["brak części", "ciągle się psuje"]},
        "search": ["niedobór", "brakuje", "podwyżki", "kolejki"], "suggest": ["gdzie kupić", "cena"],
    },
    "ro": {
        "cues": {"unmet": ["nu se găsește", "de unde cumpăr"], "unaffordable": ["prea scump", "scumpiri"],
                 "scarcity": ["lipsă de", "criză de", "penurie"], "normalized": ["listă de așteptare"], "inefficient": ["nu sunt piese"]},
        "search": ["criză de", "lipsă de", "scumpiri"], "suggest": ["de unde cumpăr", "preț"],
    },
    "el": {
        "cues": {"unmet": ["δεν βρίσκω", "πού να αγοράσω"], "unaffordable": ["πολύ ακριβό", "ακρίβεια", "αυξήσεις τιμών"],
                 "scarcity": ["ελλείψεις", "έλλειψη", "διακοπή ρεύματος"], "normalized": ["λίστα αναμονής"], "inefficient": []},
        "search": ["ελλείψεις", "ακρίβεια"], "suggest": ["πού να αγοράσω", "τιμή"],
    },
    "ta": {
        "cues": {"unmet": ["கிடைக்கவில்லை", "எங்கே வாங்குவது"], "unaffordable": ["விலை உயர்வு", "அதிக விலை"],
                 "scarcity": ["தட்டுப்பாடு", "மின்வெட்டு", "தண்ணீர் இல்லை"], "normalized": [], "inefficient": []},
        "search": ["தட்டுப்பாடு", "விலை உயர்வு", "மின்வெட்டு"], "suggest": ["எங்கே வாங்குவது", "விலை"],
    },
    "ne": {
        "cues": {"unmet": ["पाइँदैन", "कहाँ पाइन्छ"], "unaffordable": ["महँगी", "मूल्य वृद्धि"],
                 "scarcity": ["अभाव", "लोडसेडिङ", "पानी छैन"], "normalized": [], "inefficient": []},
        "search": ["अभाव", "महँगी", "मूल्य वृद्धि"], "suggest": ["कहाँ पाइन्छ", "मूल्य"],
    },
    "my": {
        "cues": {"unmet": ["မရနိုင်", "ဘယ်မှာဝယ်"], "unaffordable": ["ဈေးကြီး", "ဈေးတက်"], "scarcity": ["ပြတ်လပ်", "မီးပျက်"],
                 "normalized": [], "inefficient": []},
        "search": ["ပြတ်လပ်", "ဈေးတက်", "မီးပျက်"], "suggest": ["ဘယ်မှာဝယ်"],
    },
    "km": {
        "cues": {"unmet": ["រកមិនបាន"], "unaffordable": ["ថ្លៃពេក", "ឡើងថ្លៃ"], "scarcity": ["ខ្វះខាត", "ដាច់ភ្លើង"],
                 "normalized": [], "inefficient": []},
        "search": ["ខ្វះខាត", "ឡើងថ្លៃ"], "suggest": ["ទិញនៅណា"],
    },
    "uz": {
        "cues": {"unmet": ["topib bo'lmaydi", "qayerdan olish"], "unaffordable": ["juda qimmat", "narx oshdi"],
                 "scarcity": ["tanqislik", "yetishmovchilik", "svet o'chdi", "gaz yo'q"], "normalized": [], "inefficient": []},
        "search": ["tanqislik", "narx oshdi", "yetishmovchilik"], "suggest": ["qayerdan olish", "narxi"],
    },
    "kk": {
        "cues": {"unmet": ["табу мүмкін емес"], "unaffordable": ["қымбат", "бағасы өсті"], "scarcity": ["тапшылық", "жетіспеушілік"],
                 "normalized": [], "inefficient": []},
        "search": ["тапшылық", "бағасы өсті"], "suggest": ["қайдан алуға болады"],
    },
    "zu": {
        "cues": {"unmet": ["angitholi", "ngingakuthola kuphi"], "unaffordable": ["kubiza kakhulu", "amanani akhuphukile"],
                 "scarcity": ["ukushoda", "akukho gesi", "akukho manzi"], "normalized": [], "inefficient": []},
        "search": ["ukushoda", "load shedding", "akukho manzi"], "suggest": ["ngingakuthola kuphi"],
    },
    "af": {
        "cues": {"unmet": ["kan nie kry nie", "waar koop"], "unaffordable": ["te duur", "pryse styg"], "scarcity": ["tekort", "beurtkrag"],
                 "normalized": ["waglys"], "inefficient": []},
        "search": ["tekort", "beurtkrag", "te duur"], "suggest": ["waar koop", "prys"],
    },
}

SUPPORTED = set(L)


def cues(lang: str) -> dict[str, list[str]]:
    return L.get(lang, {}).get("cues", {})


def search_terms(lang: str, n: int = 6) -> list[str]:
    return L.get(lang, L["en"])["search"][:n]


def suggest_templates(lang: str) -> list[str]:
    return L.get(lang, L["en"])["suggest"]


def detect(text: str, langs: list[str] | None = None) -> dict[str, list[str]]:
    """Return {need_type: [matched cues]} scanning the given languages (default: all)."""
    low = (text or "").lower()
    out: dict[str, list[str]] = {}
    for lang in (langs or L.keys()):
        for typ, phrases in cues(lang).items():
            for p in phrases:
                if p and p in low:
                    out.setdefault(typ, []).append(p)
    return out


# ---- compact lexicons for the remaining languages (scarcity / price / unmet core) ----
def _c(unmet, unaff, scar, search, suggest, normalized=(), inefficient=()):
    return {"cues": {"unmet": list(unmet), "unaffordable": list(unaff), "scarcity": list(scar),
                     "normalized": list(normalized), "inefficient": list(inefficient)},
            "search": list(search), "suggest": list(suggest)}


L.update({
    "sq": _c(["nuk gjendet", "ku të blej"], ["shumë shtrenjtë", "rritje e çmimeve"], ["mungesë", "ndërprerje e energjisë"],
             ["mungesë", "rritje e çmimeve", "shtrenjtë"], ["ku të blej", "çmimi"]),
    "ca": _c(["no es troba", "on comprar"], ["massa car", "pujada de preus"], ["escassetat", "manca de", "apagada"],
             ["escassetat", "pujada de preus"], ["on comprar", "preu"], ["llista d'espera"]),
    "hy": _c(["չի գտնվում", "որտեղ գնել"], ["շատ թանկ", "գնաճ"], ["պակաս", "դեֆիցիտ"], ["դեֆիցիտ", "գնաճ"], ["որտեղ գնել", "գին"]),
    "az": _c(["tapılmır", "haradan almaq"], ["çox bahalı", "qiymət artımı"], ["çatışmazlıq", "qıtlıq", "işıq kəsilir"],
             ["çatışmazlıq", "qiymət artımı", "qıtlıq"], ["haradan almaq", "qiyməti"]),
    "bg": _c(["не може да се намери", "къде да купя"], ["много скъпо", "поскъпване"], ["недостиг", "дефицит", "липса на"],
             ["недостиг", "поскъпване", "липса на"], ["къде да купя", "цена"]),
    "hr": _c(["ne može se naći", "gdje kupiti", "nema na zalihi"], ["preskupo", "poskupljenje"], ["nestašica", "manjak"],
             ["nestašica", "poskupljenje"], ["gdje kupiti", "cijena"], ["lista čekanja"]),
    "sr": _c(["не може да се нађе", "где купити", "nema nigde"], ["прескупо", "поскупљење", "poskupljenje"],
             ["несташица", "nestašica"], ["nestašica", "poskupljenje", "несташица"], ["gde kupiti", "cena"]),
    "bs": _c(["ne može se naći", "gdje kupiti"], ["preskupo", "poskupljenje"], ["nestašica"], ["nestašica", "poskupljenje"],
             ["gdje kupiti", "cijena"]),
    "cs": _c(["nedá se sehnat", "kde koupit", "není skladem"], ["příliš drahé", "zdražování"], ["nedostatek", "výpadek"],
             ["nedostatek", "zdražování", "nedá se sehnat"], ["kde koupit", "cena"], ["čekací lhůta", "pořadník"]),
    "sk": _c(["nedá sa zohnať", "kde kúpiť"], ["príliš drahé", "zdražovanie"], ["nedostatok", "výpadok"],
             ["nedostatok", "zdražovanie"], ["kde kúpiť", "cena"]),
    "sl": _c(["ni mogoče dobiti", "kje kupiti"], ["predrago", "podražitev"], ["pomanjkanje"], ["pomanjkanje", "podražitev"],
             ["kje kupiti", "cena"], ["čakalna doba"]),
    "da": _c(["kan ikke finde", "hvor køber man"], ["alt for dyrt", "prisstigning"], ["mangel på", "udsolgt"],
             ["mangel på", "prisstigning", "ventelister"], ["hvor køber man", "pris"], ["venteliste"]),
    "sv": _c(["går inte att hitta", "var köper man"], ["alldeles för dyrt", "prishöjning"], ["brist på", "slutsålt"],
             ["brist på", "prishöjning", "vårdköer"], ["var köper man", "pris"], ["vårdköer", "väntetid"]),
    "no": _c(["finner ikke", "hvor kjøper man"], ["altfor dyrt", "prisøkning"], ["mangel på", "utsolgt"],
             ["mangel på", "prisøkning", "venteliste"], ["hvor kjøper man", "pris"], ["venteliste", "ventetid"]),
    "nb": _c(["finner ikke", "hvor kjøper man"], ["altfor dyrt", "prisøkning"], ["mangel på", "utsolgt"],
             ["mangel på", "prisøkning"], ["hvor kjøper man", "pris"], ["venteliste"]),
    "fi": _c(["ei löydy", "mistä ostaa"], ["liian kallis", "hinnankorotus"], ["pula", "loppuunmyyty"],
             ["pula", "hinnankorotus", "jonot"], ["mistä ostaa", "hinta"], ["hoitojono", "jonotus"]),
    "et": _c(["ei leia", "kust osta"], ["liiga kallis", "hinnatõus"], ["puudus", "nappus"], ["puudus", "hinnatõus"],
             ["kust osta", "hind"], ["järjekord"]),
    "lv": _c(["nevar atrast", "kur nopirkt"], ["pārāk dārgi", "cenu kāpums"], ["trūkums", "deficīts"],
             ["trūkums", "cenu kāpums"], ["kur nopirkt", "cena"], ["rinda"]),
    "lt": _c(["negaliu rasti", "kur nusipirkti"], ["per brangu", "kainų kilimas"], ["trūkumas", "stygius"],
             ["trūkumas", "kainų kilimas"], ["kur nusipirkti", "kaina"], ["eilės"]),
    "hu": _c(["nem kapható", "hol lehet venni"], ["túl drága", "áremelés", "drágulás"], ["hiány", "áramszünet"],
             ["hiány", "drágulás", "áremelés"], ["hol lehet venni", "ár"], ["várólista", "hónapokat várni"]),
    "is": _c(["finn ekki", "hvar kaupir maður"], ["allt of dýrt", "verðhækkun"], ["skortur"], ["skortur", "verðhækkun"],
             ["hvar kaupir maður", "verð"], ["biðlisti"]),
    "ka": _c(["ვერ ვპოულობ", "სად ვიყიდო"], ["ძალიან ძვირი", "გაძვირება"], ["დეფიციტი", "ნაკლებობა"],
             ["დეფიციტი", "გაძვირება"], ["სად ვიყიდო", "ფასი"]),
    "mk": _c(["не може да се најде", "каде да купам"], ["прескапо", "поскапување"], ["недостиг", "дефицит"],
             ["недостиг", "поскапување"], ["каде да купам", "цена"]),
    "mn": _c(["олдохгүй", "хаанаас авах"], ["хэтэрхий үнэтэй", "үнийн өсөлт"], ["хомсдол", "дутагдал"],
             ["хомсдол", "үнийн өсөлт"], ["хаанаас авах", "үнэ"]),
    "lo": _c(["ຫາບໍ່ໄດ້", "ຊື້ຢູ່ໃສ"], ["ແພງຫຼາຍ", "ລາຄາຂຶ້ນ"], ["ຂາດແຄນ", "ໄຟຟ້າດັບ"], ["ຂາດແຄນ", "ລາຄາຂຶ້ນ"], ["ຊື້ຢູ່ໃສ", "ລາຄາ"]),
    "tk": _c(["tapyp bolanok", "nireden almaly"], ["gaty gymmat", "nyrh ýokarlandy"], ["ýetmezçilik", "kemçilik"],
             ["ýetmezçilik", "gymmat"], ["nireden almaly", "bahasy"]),
    "dv": _c([], ["ވަރަށް އަގުބޮޑު"], ["ހުސްވެފަ"], ["ހުސްވެފަ"], []),
    "ht": _c(["pa jwenn", "ki kote pou achte"], ["twò chè", "lavichè"], ["mank", "rarete", "pa gen kouran", "pa gen dlo"],
             ["mank", "lavichè", "rarete"], ["ki kote pou achte", "pri"]),
    "qu": _c([], [], ["pisiy"], [], []),
})
SUPPORTED = set(L)
