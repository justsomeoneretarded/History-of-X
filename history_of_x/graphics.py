"""Original source-linked explanatory graphics; no generated historical evidence."""
from PIL import Image,ImageDraw
from .maps import font

def make(kind,output):
    width,height=1920,1080
    im=Image.new('RGB',(width,height),(11,22,31));d=ImageDraw.Draw(im)
    for x in range(0,width,120):d.line((x,0,x,height),fill=(17,31,41),width=1)
    for y in range(0,height,120):d.line((0,y,width,y),fill=(17,31,41),width=1)
    gold=(229,187,102);light=(239,241,237);muted=(167,183,190)
    if kind=='wuchale':
        title='ONE TREATY. TWO MEANINGS.';subtitle='Article 17 · meanings summarized in English'
        cards=[('AMHARIC VERSION','An option',['Ethiopia could use Italian','diplomatic channels.']),
               ('ITALIAN VERSION','An obligation',['Italy claimed control over','Ethiopian foreign relations.'])]
        footer='Paraphrase · Treaty of Wuchale, 1889 · see documentary sources'
    elif kind=='transition':
        title='AFTER THE DERG';subtitle='Two dates that reshaped the region'
        cards=[('1991','The Derg falls',['A military government','loses power.']),
               ('1993','Eritrean independence',['A referendum leads','to a new sovereign state.'])]
        footer='Historical timeline · see documentary sources'
    else:raise ValueError('Unknown original graphic')
    d.text((140,170),title,font=font(64,True),fill=gold)
    d.text((145,265),subtitle,font=font(30),fill=muted)
    for i,(label,heading,lines) in enumerate(cards):
        x=140+i*860
        d.rounded_rectangle((x,360,x+780,785),radius=16,fill=(23,39,50),outline=gold,width=2)
        d.text((x+50,405),label,font=font(32,True),fill=gold)
        d.text((x+50,480),heading,font=font(48,True),fill=light)
        for j,line in enumerate(lines):d.text((x+50,585+j*52),line,font=font(32),fill=muted)
    d.text((145,860),footer,font=font(25),fill=muted)
    im.save(output,quality=96)
    return output
