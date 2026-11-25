"""Original reusable illustration assets for model-directed history animation.

These are our own character designs, never traced reference-video characters.
No actor contains an automatic idle, walking or reaction loop.
"""
from __future__ import annotations
from html import escape

VERSION = "original-history-cast-v1"
PALETTE = {"ink":"#293631","cream":"#F4E6C8","gold":"#D5AD58",
           "teal":"#34756F","rust":"#B85F47","blue":"#36546C"}

CAST = {
 "menelik": ("#A7704B","#242725","#22675F","#D6B25D","royal","full","diadem"),
 "taytu": ("#AA704C","#272322","#ECE0C1","#B99448","dress","none","wrap"),
 "italian_officer": ("#D1A482","#66594D","#354D65","#C5A350","military","moustache","kepi"),
 "aksum_merchant": ("#A36B45","#302B24","#B8794C","#E8CE94","robe","short","cloth"),
 "highland_ruler": ("#98613F","#282723","#5B506D","#D6B25D","royal","full","diadem"),
 "haile_selassie": ("#AC7650","#282925","#B59B6D","#D0AD55","military","short","none"),
 "derg_officer": ("#976144","#292823","#5F7155","#B65340","military","moustache","cap"),
 "modern_official": ("#9C6848","#282928","#344B5A","#BD9151","suit","short","none"),
 "european_official": ("#CEA27C","#71604D","#526070","#A95643","suit","moustache","none"),
 "civilian": ("#A87550","#2D2B25","#668277","#E8D7B3","robe","short","none"),
 "civilian_woman": ("#A16B49","#2C2925","#A34D43","#E9D7B0","dress","none","cloth"),
 "roman": ("#BB8A65","#41352C","#E5D7B7","#A14B3A","robe","short","laurel"),
}
EXPRESSIONS = ("neutral","confident","worried","angry","surprised","sad")
SETTINGS = ("mountains","mountains_night","tent","port","court","rock_church","village","village_dry","city","assembly","diagram")
PROPS = ("paper","table","coin","sack","crate","rifle","cross","stele","ship",
         "crown","throne","grain","ballot_box","flag","hammer","territory")

def path(d, fill, stroke="#293631", width=3):
 return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'

def actor_parts(appearance):
 skin,hair,cloth,trim,outfit,beard,hat=CAST[appearance]
 ink=PALETTE["ink"]
 # Each component has its own true joint. Coordinates use a 360x760 rig.
 legs=[]
 for side,x in (("back",130),("front",230)):
  leg=path(f"M{x-28} 552 Q{x-34} 618 {x-22} 690 L{x+24} 690 L{x+27} 558Z","#39423D")
  leg+=path(f"M{x-22} 680 L{x-24} 737 Q{x-30} 751 {x-13} 752 H{x+55} Q{x+63} 738 {x+32} 728 L{x+23} 680Z","#3E3029")
  leg+=f'<path d="M{x-12} 691V727" stroke="#77624B" stroke-width="4"/>'
  legs.append((f"leg_{side}",leg,"torso",(x,555)))
 if outfit in ("robe","royal","dress"):
  torso=path("M102 267 Q74 300 67 366 L58 608 Q170 647 303 609 L288 363 Q280 300 259 267 L230 252 H128Z",cloth)
  torso+=path("M132 260 L174 355 L230 260 L254 607 Q174 629 98 603Z","#F0E1BD" if outfit=="dress" else cloth)
  torso+=f'<path d="M128 276L172 352L230 276 M100 338L116 600 M244 337L232 603 M154 390L142 605 M193 389L206 606" fill="none" stroke="{trim}" stroke-width="5"/>'
  torso+=f'<path d="M106 605Q177 624 254 606" fill="none" stroke="{trim}" stroke-width="13"/>'
  if outfit=="royal":
   torso=path("M95 270 Q44 325 48 602 L110 616 L139 284Z","#8D3D3E")+torso
   torso+=path("M226 265L281 282L310 603L254 614Z","#8D3D3E")
   torso+=f'<path d="M118 282 Q176 373 244 282" fill="none" stroke="{trim}" stroke-width="9"/>'
   torso+=f'<circle cx="183" cy="330" r="12" fill="{trim}" stroke="{ink}" stroke-width="2"/>'
 else:
  torso=path("M106 267 Q76 285 67 352 L75 570 L284 570 L293 352 Q285 285 254 267 L227 254 H132Z",cloth)
  torso+=path("M128 257L179 324L232 257L219 368L181 405L142 367Z","#E9DCC1")
  torso+=path("M172 312L188 312L201 413L180 435L158 413Z",trim)
  torso+=f'<path d="M180 428V566 M91 391H148 M214 391H272 M81 546H279" stroke="{ink}" stroke-width="3" fill="none"/>'
  if outfit=="military":
   torso+=f'<path d="M80 300L123 288M237 288L280 300" stroke="{trim}" stroke-width="15"/>'
   torso+=f'<path d="M91 365H140M219 365H268" stroke="{trim}" stroke-width="5"/>'
   torso+="".join(f'<circle cx="185" cy="{y}" r="4" fill="{trim}"/>' for y in (437,468,499,530))
   torso+=f'<path d="M213 320L239 343L218 364" fill="none" stroke="{trim}" stroke-width="7"/>'
 # A shaped jaw, ears, hair, nose and period accessories replace anonymous circles.
 head=path("M126 65 Q177 40 232 68 Q258 105 250 166 L240 206 Q220 242 181 249 Q145 242 123 208 L111 162 Q104 106 126 65Z",skin)
 head+=f'<ellipse cx="111" cy="155" rx="11" ry="23" fill="{skin}" stroke="{ink}" stroke-width="3"/><ellipse cx="250" cy="155" rx="11" ry="23" fill="{skin}" stroke="{ink}" stroke-width="3"/>'
 head+=path("M111 132Q98 82 131 64Q144 35 179 46Q209 35 234 63Q268 73 251 136L234 105Q180 77 128 111Z",hair)
 head+=f'<path d="M176 137L166 178L185 181" fill="none" stroke="#714C37" stroke-width="4"/>'
 if beard=="full":
  head+=path("M119 180Q142 193 155 183L180 201L209 183Q226 195 244 180Q238 237 182 262Q127 240 119 180Z",hair)
  head+=f'<path d="M151 221Q181 234 210 218" fill="none" stroke="#74644B" stroke-width="3"/>'
 elif beard=="short":
  head+=path("M123 192L144 203L159 198L180 214L204 198L221 201L240 191Q230 238 182 252Q137 240 123 192Z",hair,width=2)
 elif beard=="moustache":
  head+=path("M142 188Q165 174 180 185Q198 174 221 188L211 202L183 195L156 202Z",hair,width=2)
 if hat in ("cloth","wrap"):
  head+=path("M104 109Q99 62 125 44Q178 10 231 48Q263 67 259 111L226 91Q176 77 130 98Z","#EBDAB8")
  head+=f'<path d="M114 71Q184 42 248 85M113 90Q176 66 255 104" fill="none" stroke="#BBA984" stroke-width="5"/>'
  if hat=="wrap": head+=path("M115 99L90 126L105 284L136 269L127 113Z","#EBDAB8")
 elif hat in ("kepi","cap"):
  head+=path("M111 92L118 35Q184 18 242 39L250 94Z",cloth)
  head+=path("M107 90Q180 75 254 94L274 110Q180 126 104 107Z","#293B43")
  head+=f'<path d="M120 72H242" stroke="{trim}" stroke-width="7"/><circle cx="184" cy="63" r="10" fill="{trim}"/>'
 elif hat=="diadem":
  head+=f'<path d="M119 89Q179 56 241 88" fill="none" stroke="{trim}" stroke-width="14"/><path d="M171 69L181 45L192 70" fill="{trim}" stroke="{ink}" stroke-width="2"/>'
 elif hat=="laurel":
  head+="".join(f'<ellipse cx="{x}" cy="{y}" rx="8" ry="15" fill="#7B8B50" transform="rotate({r} {x} {y})"/>' for x,y,r in ((125,86,-45),(143,68,-30),(219,69,30),(237,88,45)))
 torso=path("M150 225H211V290H150Z",skin,width=2)+torso
 parts=[("shadow",'<ellipse cx="180" cy="750" rx="145" ry="18" fill="#263A31" opacity=".16"/>',"torso",(180,760))]+legs+[("torso",torso,"",(180,760))]
 for side,x in (("back",90),("front",270)):
  upper=path(f"M{x} 282 Q{x-22} 294 {x-24} 327 L{x-20} 412 H{x+20} L{x+23} 324 Q{x+20} 297 {x} 282Z",cloth)
  upper+=f'<path d="M{x-12} 306V398" stroke="{trim}" stroke-width="4"/>'
  fore=path(f"M{x-20} 403L{x-17} 510L{x+18} 510L{x+20} 403Z",cloth)
  fore+=f'<path d="M{x-17} 499H{x+18}" stroke="{trim}" stroke-width="9"/>'
  fore+=path(f"M{x-14} 507Q{x-24} 519 {x-17} 540L{x-9} 552L{x+17} 545L{x+22} 528L{x+13} 511Z",skin,width=2)
  fore+=f'<path d="M{x-8} 529L{x-5} 544M{x+2} 527L{x+4} 542M{x+11} 528L{x+12} 538" stroke="#75513C" stroke-width="2"/>'
  parts += [(f"upper_{side}",upper,"torso",(x,280)),
            (f"forearm_{side}",fore,f"upper_{side}",(x,410))]
 parts.append(("head",head,"torso",(180,240)))
 for expression in EXPRESSIONS:
  eyes=""
  for x in (145,216):
   if expression=="sad":
    eyes+=f'<path d="M{x-12} 150Q{x} 141 {x+12} 150" stroke="{ink}" stroke-width="4" fill="none"/>'
   else:
    ry=11 if expression=="surprised" else 7
    eyes+=f'<ellipse cx="{x}" cy="147" rx="13" ry="{ry}" fill="#EBDAC0"/><ellipse cx="{x+2}" cy="147" rx="5" ry="{ry-1}" fill="#272927"/>'
  brows={"neutral":"M132 128L158 125M203 125L229 128",
         "confident":"M131 126Q147 115 160 124M202 124L231 119",
         "worried":"M131 130L159 117M202 117L231 130",
         "angry":"M131 117L160 132M201 132L231 117",
         "surprised":"M131 113L159 111M202 111L231 113",
         "sad":"M132 131L159 119M202 119L229 131"}[expression]
  eyes+=f'<path d="{brows}" fill="none" stroke="{hair}" stroke-width="6" stroke-linecap="round"/>'
  if expression=="surprised": eyes+='<ellipse cx="182" cy="208" rx="10" ry="13" fill="#724A35"/>'
  else:
   mouth={"neutral":"M163 209Q182 215 201 208","confident":"M162 207Q186 222 207 204",
          "worried":"M165 216Q182 204 202 214","angry":"M161 214L202 211",
          "sad":"M164 219Q182 208 201 218"}[expression]
   eyes+=f'<path d="{mouth}" fill="none" stroke="#6B4231" stroke-width="4" stroke-linecap="round"/>'
  parts.append((f"face_{expression}",eyes,"head",(180,150)))
 return parts

def background(setting):
 sky='<rect width="1920" height="1080" fill="#F1DFC0"/>'
 if setting=="diagram":
  return sky+'<ellipse cx="960" cy="952" rx="800" ry="80" fill="#C3B18F" opacity=".18"/>'
 if setting=="tent":
  return '<rect width="1920" height="1080" fill="#7D7157"/><path d="M0 0L960 150L1920 0V980H0Z" fill="#BBA47B"/><path d="M0 0L300 1080M1920 0L1650 1080M960 150V1080" stroke="#6F5A3F" stroke-width="16"/><path d="M600 180H1280V760H600Z" fill="#233C4A"/><path d="M600 650L810 430L990 610L1180 440L1280 670V760H600Z" fill="#526C69"/><path d="M0 920H1920V1080H0Z" fill="#8B7754"/><path d="M0 0L600 180L560 840L100 980Z M1920 0L1280 180L1320 840L1830 980Z" fill="#C4AF87"/><path d="M170 120L490 860M1750 120L1390 860" stroke="#A38B64" stroke-width="7"/>'
 if setting in ("court","assembly"):
  modern=setting=="assembly"
  wall="#DCE1D8" if modern else "#D4B58D"
  art=f'<rect width="1920" height="1080" fill="{wall}"/><path d="M0 870H1920V1080H0Z" fill="#88735A"/>'
  for x in (105,1490):
   d=f"M{x} 700V285Q{x} 135 {x+155} 125Q{x+310} 135 {x+310} 285V700Z"
   art+=path(d,"#4B594D" if modern else "#76553D",width=5)
   art+=path(f"M{x+22} 677V288Q{x+22} 162 {x+155} 150Q{x+288} 162 {x+288} 288V677Z","#B7D4CF",width=0)
   art+=f'<path d="M{x+23} 534L{x+100} 438L{x+170} 510L{x+240} 415L{x+287} 490V676H{x+23}Z" fill="#749581"/>'
   art+=f'<path d="M{x+155} 155V680" stroke="#76553D" stroke-width="9"/>'
  art+=f'<path d="M0 75H1920M0 102H1920M485 148H1415M485 181H1415" stroke="#88694A" stroke-width="{10 if modern else 18}"/>'
  art+='<path d="M0 870H1920M0 1005H1920M400 870L200 1080M1520 870L1730 1080M960 870V1080" stroke="#594D3D" stroke-width="3"/>'
  if not modern: art+='<path d="M520 1080L640 888H1275L1420 1080Z" fill="#A75342"/><path d="M565 1058L661 912H1252L1366 1058Z" stroke="#DBB768" stroke-width="8" fill="none"/>'
  for x in (70,1780):
   art+=f'<path d="M{x} 805L{x-35} 590L{x+20} 550L{x+84} 610L{x+105} 805Z" fill="#5E7953"/><path d="M{x-15} 795H{x+115}L{x+95} 902H{x+5}Z" fill="#AA7047" stroke="#785137" stroke-width="4"/>'
  return art
 if setting=="port":
  art=sky+'<path d="M0 450L250 340L450 427L640 310L920 451L1210 330L1480 440L1770 338L1920 450V700H0Z" fill="#93ADA0"/>'
  art+='<path d="M640 512H1920V1020H540Z" fill="#78ADA7"/><path d="M760 622H1920M900 746H1840M1000 851H1920" stroke="#B1CCC0" stroke-width="5"/>'
  art+='<path d="M0 600Q420 530 640 610Q550 800 810 1080H0Z" fill="#D3B387"/><path d="M430 730L1250 755L1280 850L455 815Z" fill="#9A714B" stroke="#5F4B38" stroke-width="7"/>'
  art+=''.join(f'<path d="M{x} 748L{x+15} 821" stroke="#6B523B" stroke-width="5"/>' for x in range(480,1240,85))
  for x,y,w in ((60,420,200),(300,400,160),(445,460,150)):
   art+=path(f"M{x} {y}H{x+w}V{y+180}H{x}Z","#C7AC83",width=4)
   art+=f'<path d="M{x-10} {y}H{x+w+10}" stroke="#8B6E4A" stroke-width="14"/>'
   art+=f'<path d="M{x+40} {y+55}H{x+75}V{y+130}H{x+40}Z" fill="#665C42"/>'
  return art
 if setting=="rock_church":
  return sky+path("M0 400L300 290L560 365L920 220L1260 335L1620 280L1920 430V1080H0Z","#B8895B")+path("M710 350H1240V435H1390V705H1240V835H710V705H550V435H710Z","#934F36")+path("M755 393H1195V480H1340V661H1195V790H755V661H595V480H755Z","#BE7950")+''.join(f'<path d="M{x} 510V640" stroke="#593F30" stroke-width="18"/>' for x in (800,900,1000,1100))+'<path d="M0 934L500 870L560 1080H0Z M1380 1080L1450 870L1920 928V1080Z" fill="#D7B78B"/>'
 if setting in ("village","village_dry"):
  dry=setting=="village_dry"
  art=sky+f'<path d="M0 504L300 406L600 483L920 393L1250 500L1550 400L1920 510V1080H0Z" fill="{"#C3AC79" if dry else "#9BB084"}"/>'
  art+=f'<path d="M0 780Q800 686 1920 795V1080H0Z" fill="{"#CCAA75" if dry else "#B5B77A"}"/>'
  for x,y,s in ((95,545,1),(1370,575,.85),(1580,530,1.1)):
   art+=f'<g transform="translate({x} {y}) scale({s})">'+path("M0 100Q100 65 200 100V290Q105 321 0 290Z","#BB8E5B")+path("M-25 108L100-20L225 108Q104 155-25 108Z","#80663C")+path("M72 215Q100 185 130 215V300H72Z","#5E4A33")+'</g>'
  art+='<path d="M0 990Q600 860 1050 970T1920 940" fill="none" stroke="#DBC79C" stroke-width="54"/>'
  return art
 if setting=="city":
  art=sky+'<path d="M0 570H1920V1080H0Z" fill="#A3ACA0"/><path d="M780 565H1120L1500 1080H400Z" fill="#C5B590"/>'
  for x,w,h in ((0,240,280),(255,210,355),(470,260,235),(1260,240,250),(1515,180,370),(1710,210,295)):
   art+=path(f"M{x} {600-h}H{x+w}V870H{x}Z","#BAA986",width=4)
   for y in range(650-h,800,78):
    for xx in range(x+28,x+w-20,68):
     art+=f'<rect x="{xx}" y="{y}" width="30" height="44" fill="#55675E"/><path d="M{xx-5} {y+46}H{xx+35}" stroke="#DFD1AF" stroke-width="5"/>'
  return art
 # Deliberately layered, geographically nonspecific uplands, never a border map.
 if setting=="mountains_night":sky=sky.replace("#F1DFC0","#1D3346")+'<circle cx="1610" cy="175" r="46" fill="#E3D5AE"/>'
 return sky+'<path d="M0 515L190 365L430 490L700 300L970 485L1240 315L1480 480L1710 320L1920 490V1080H0Z" fill="#92A491"/><path d="M0 690L300 470L580 660L930 445L1210 670L1500 475L1920 690V1080H0Z" fill="#637F76"/><path d="M0 920L350 720L700 930L1050 715L1440 932L1780 750L1920 830V1080H0Z" fill="#927D56"/><path d="M0 1000Q570 860 880 973T1920 920" fill="none" stroke="#C0A77C" stroke-width="72"/><path d="M40 1035L70 1010L65 1050M1600 1030L1635 992L1645 1048" stroke="#5B6B48" stroke-width="12" fill="none"/>'

def prop_art(kind, text=""):
 ink="#293631";gold="#D6B15D"
 if kind=="paper_flat":
  art=path("M0-45H160L200 15H-20Z","#F6E8C8",width=3)
  art+='<path d="M17-31H145M13-22H137" stroke="#BAA276" stroke-width="2"/>'
  if text:art+=f'<text x="92" y="3" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="20" fill="#365B53">{escape(text[:22])}</text>'
  return art
 if kind=="paper":
  art=path("M0-120L185-115L193 8L-5 14Z","#F6E8C8",width=3)
  art+='<path d="M15-94H167M15-80H152M15-64H169" stroke="#BAA276" stroke-width="3"/><circle cx="162" cy="-5" r="12" fill="#A74D3A"/>'
  if text: art+=f'<text x="94" y="-22" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="30" fill="#365B53">{escape(text[:22])}</text>'
  return art
 if kind=="table":
  return path("M-370 0L-260-65H270L370 0L335 80H-340Z","#AE7A4E")+path("M-340 80H335V115H-340Z","#674A32")+path("M-270 110L-300 300H-250L-205 110M205 110L250 300H300L270 110Z","#674A32")+'<path d="M-300 0H290M-250 27H315" stroke="#D1A16D" stroke-width="4"/>'
 if kind=="coin":
  return f'<circle cy="-30" r="49" fill="{gold}" stroke="#9C7137" stroke-width="6"/><circle cy="-30" r="37" fill="none" stroke="#F4D692" stroke-width="4"/><path d="M-8-55L16-41L7-21L-13-15L-22-35Z" fill="#B0803D"/><path d="M-21-4H23" stroke="#B0803D" stroke-width="5"/>'
 if kind in ("sack","grain"):
  art=path("M-30-112Q0-95 30-112L19-84Q72-22 50 6Q0 30-51 5Q-72-22-19-84Z","#BEA06B")
  art+='<path d="M-28-84H27M-38-34L-28 3M28-40L36 1" stroke="#8F764E" stroke-width="5"/>'
  if kind=="grain": art+=''.join(f'<ellipse cx="{x}" cy="{y}" rx="6" ry="12" transform="rotate(30 {x} {y})" fill="#E4C16C"/>' for x,y in ((-10,-50),(10,-40),(-22,-20),(2,-14),(24,-5)))
  return art
 if kind=="crate":
  return path("M-65-110H65V20H-65Z","#A87849")+'<path d="M-55-99L55 8M55-99L-55 8M-65-55H65" stroke="#6E5134" stroke-width="10"/>'
 if kind=="rifle":
  return path("M-14 14L-11-65L-5-85L-6-185H6L7-85L15-68L13 14Z","#6C4A31")+'<path d="M0-185V-79" stroke="#394548" stroke-width="7"/><path d="M-3-52Q25-59 18-25H-3" fill="none" stroke="#394548" stroke-width="5"/>'
 if kind=="cross":
  return path("M-13-170H13V-125H52V-99H13V15H-13V-99H-52V-125H-13Z",gold)
 if kind=="stele":
  art=path("M-55 0L-43-340Q0-385 43-340L55 0Z","#9D9E87")
  art+='<path d="M-34-322H33M-37-272H36M-41-220H40M-44-168H43M-48-114H47" stroke="#676F62" stroke-width="5"/>'
  art+=''.join(f'<rect x="-22" y="{y}" width="44" height="26" fill="#697567"/>' for y in (-305,-253,-201,-149,-97))
  return art
 if kind=="ship":
  return path("M-210-10Q-110 80 160 38L222-25Q30 9-210-10Z","#805736",width=5)+'<path d="M0-8V-261" stroke="#5D4D36" stroke-width="11"/>'+path("M-9-246Q-75-183-13-53L-173-71Q-182-183-9-246Z","#ECE2BD")+path("M12-239L171-90L15-59Z","#CFD6BB")+'<path d="M-145 19Q0 49 171 11" stroke="#D4B77E" stroke-width="5" fill="none"/>'
 if kind=="crown":
  return path("M-75-70L-52-18H53L76-72L30-49L0-91L-29-49Z",gold)+'<path d="M-52-13H54" stroke="#9A733A" stroke-width="12"/><circle cy="-49" r="10" fill="#4A8074"/>'
 if kind=="throne":
  return path("M-95 0V-274Q0-354 95-274V0Z","#AA6848",width=5)+path("M-74-20V-264Q0-320 74-264V-20Z","#9A3E3A")+path("M-120-60H120V-15H-120Z",gold)+'<path d="M-84-5V85M84-5V85" stroke="#715036" stroke-width="20"/>'
 if kind=="ballot_box":
  return path("M-70-110H70V20H-70Z","#79988B")+'<path d="M-25-110H27" stroke="#293631" stroke-width="9"/>'+path("M-19-166H34V-109H-19Z","#EEE0BD",width=2)
 if kind=="flag":
  return '<path d="M0 20V-220" stroke="#6D5338" stroke-width="9"/>'+path("M4-211Q60-231 130-204V-113Q70-140 4-119Z","#B45242")
 if kind=="hammer":
  return '<path d="M0 12L20-140" stroke="#92704A" stroke-width="14"/>'+path("M-39-147L65-137L62-109L-42-119Z","#63716A")
 if kind=="territory":
  return path("M-105-50L-40-100L20-80L87-110L120-20L85 65L17 95L-82 56Z","#76A18F",width=5)
 raise ValueError("Unknown original prop")
