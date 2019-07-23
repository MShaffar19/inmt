from __future__ import unicode_literals

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

from .models import *

import re

import json

import re
import ast

import sys
import os
dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(dir_path, 'opennmt'))

from itertools import repeat

from onmt.utils.logging import init_logger
from onmt.utils.misc import split_corpus
from onmt.translate.infertranslator import build_translator

import onmt.opts as opts
from onmt.utils.parse import ArgumentParser

import pickle
import random

from indic_transliteration import sanscript
from indic_transliteration.sanscript import SchemeMap, SCHEMES, transliterate

import csv

import requests

with open(os.path.join(dir_path, 'opt_data'), 'rb') as f:
        opt = pickle.load(f)

langspecs = {
    '2' : {
        'src' : 'en',
        'tgt' : 'hi',
        'model': 'full_iitb_enhi_50v.pt',
        'indic_code': sanscript.DEVANAGARI,
        'provide_help' : True,
    },
    '1' : {
        'src' : 'hi',
        'tgt' : 'en',
        'model': 'full_iitb_bpe_hien.pt',
        'indic_code': None,
        'provide_help' : False,
    }
}

translatordict = {}

for k, v in langspecs.items():
    opt.models = [os.path.join(dir_path, 'model', v["model"])]
    opt.n_best = 1
    opt.max_length = 100
    ArgumentParser.validate_translate_opts(opt)
    logger = init_logger(opt.log_file)
    translatorbest = build_translator(opt, report_score=True)

    opt.models = [os.path.join(dir_path, 'model', v["model"])]
    opt.n_best = 5
    opt.max_length = 2
    ArgumentParser.validate_translate_opts(opt)
    logger = init_logger(opt.log_file)
    translatorbigram = build_translator(opt, report_score=True)

    translatordict[k] = {"translatorbest": translatorbest, "translatorbigram": translatorbigram}


def index(request):
    return render(request, 'index.html')

@login_required
def export_keystroke_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="keystrokes.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Corpus', 'Keystrokes'])
    users = User.objects.all()

    for user in users:
        translatedsets = translatedSet.objects.filter(user=user)
        for tset in translatedsets:
            try:
                writer.writerow([user.translator.name, tset.corpus.name, tset.dockeystroke.keystrokeseries])
            except:
                pass
    return response


@login_required
def tstart(request):
    request.session["translatedsetid"] = 0
    translatorlangs = request.user.translator.translatorlangs.values('langtolang')
    all_corpus = corpus.objects.filter(corpuslangreqs__langtolang__in=translatorlangs).order_by('id')

    corp = []
    for i in range(len(all_corpus)):
        percorp = {}
        percorp["name"] = all_corpus[i].name
        percorp["baselang"] = all_corpus[i].baselang
        percorp["id"] = all_corpus[i].id
        langtolangs = all_corpus[i].corpuslangreqs.values_list('langtolang__src__name', 'langtolang__tgt__name', 'langtolang__id')
        
        translatorlangsid = [k['langtolang'] for k in list(translatorlangs)]
        for langtolangdesc in langtolangs:
            if langtolangdesc[2] in translatorlangsid:
                percorp["langtolang"] = langtolangdesc[0] + " --> " + langtolangdesc[1]
                percorp["langtolangid"] = langtolangdesc[2]
                

                ## Check for translated set
                transsent = translatedSentence.objects.filter(translatedSet__in=translatedSet.objects.filter(corpus=all_corpus[i], user=request.user, langtolang=langtolang.objects.get(pk=langtolangdesc[2])))
                if transsent.count() == 0:
                    condition = 0
                else:
                    vlist = list(transsent.values_list('tgt', flat=True))
                    if '' in vlist:
                        condition = 1
                    else:
                        condition = 2
                percorp["condition"] = condition

                corp.append(percorp)
    context = {
        'corpus': corp,
        }
    return render(request, 'tstart.html', context)


def transdelete(request):
    corpid = request.GET.get('corpid')
    langtolangid = request.GET.get('langtolangid')
    corp = corpus.objects.get(pk=corpid)
    translatedSet.objects.filter(user=request.user, corpus=corp, langtolang=langtolang.objects.get(pk=langtolangid)).delete()
    return JsonResponse({'result': 'hello'})

@login_required
def dashboard(request):
    request.session["translatedsetid"] = 0
    return render(request, 'dashboard.html')


# def login(request):
#     pass

# def logout(request):
#     pass

# def logint(request):
#     pass

@login_required
def new(request):
    # global translatedsetid
    if request.session['translatedsetid'] == 0:
        return redirect('/corpus')
    
    if translatedSet.objects.get(pk=request.session['translatedsetid']).corpus.helpprovision:
        return render(request, 'inmt.html')
    else:
        return render(request, 'inmth.html')


@login_required
def corpusinput(request):
    corpid = request.POST.get('corpid')
    langtolangid = request.POST.get('langtolangid')

    request.session['langtolangid'] = langtolangid
    request.session['corpusid'] = corpid
    

    
    corp = corpus.objects.get(pk=corpid)
    translatedsets, created = translatedSet.objects.update_or_create(user=request.user, corpus=corp, langtolang=langtolang.objects.get(pk=langtolangid))
    request.session['translatedsetid'] = translatedsets.id
    for i in corp.corpusdivide.all():
        # translatedsent, created = translatedSentence.objects.get_or_create(translatedSet=translatedsets, src=i.src)
        # if created:
        #     translatedsent.tgt = ''
        #     translatedsent.save()
        translatedsent, created = translatedSentence.objects.get_or_create(translatedSet=translatedsets, src=i.src)
        # if created:
        translatedsent.tgt = ''
        translatedsent.save()
    return HttpResponse('Success')

@login_required
def getinput(request):
    translatedsents = translatedSentence.objects.filter(translatedSet__id=request.session['translatedsetid']).order_by('id')
    corpusinps = []
    for i in translatedsents:
        corpusinps.append([i.src, i.tgt])
    return JsonResponse({'result': corpusinps})


def quotapos(s, lang="en"):
    s = re.sub(r"&quot;", r'"', s)
    return re.sub(r"&apos;", r"'", s)

def quotaposr(s, lang="en"):
    s = re.sub(r'"', r'&quot;', s)
    return re.sub(r"'", r"&apos;", s)

@login_required
def translate_new(request):
    L1 = request.GET.get('a').strip()
    L2 = quotaposr(request.GET.get('b', ""))
    L2split = L2.split()

    langtolangid = request.session['langtolangid']

    if langspecs[langtolangid]['indic_code']:
        if L2 != '' and bool(re.search(r"([^\s\u0900-\u097F])", L2[-1])):
            params = {}
            params['inString'] = L2split[-1]
            params['lang'] = 'hindi'
            data = requests.get('http://xlit.quillpad.in/quillpad_backend2/processWordJSON', params = params).json()
            L2split[-1] = data['twords'][0]['options'][0]
            L2 = ' '.join(L2split)
    
    _, pred, covatn2d = translatordict[langtolangid]['translatorbest'].translate(
        src=[L1],
        tgt=None,
        src_dir='',
        batch_size=30,
        attn_debug=True,
        partial = L2
        )

    scores, predictions = translatordict[langtolangid]['translatorbigram'].translate(
        src=[L1],
        tgt=None,
        src_dir='',
        batch_size=30,
        attn_debug=False,
        partial = L2,
        dymax_len = 2,
        )


    # print(covatn2d)
    if L2 != '':
        attn = covatn2d[:len(L2.strip().split(" "))]
        sumattn = [sum(i) for i in zip(*attn)]
        for i in range(len(attn)):
            if max(attn[i]) > 0.30:
                sumattn[attn[i].index(max(attn[i]))] = 1
            print(max(attn[i]))
        newattn = [float("{0:.2f}".format(1-(k/max(sumattn)))) for k in sumattn]
        # sumattn = [float("{0:.2f}".format(k/sum(newattn))) for k in newattn]
        newattn = [ 1.66*max(0, (k-0.4)) for k in newattn]
        sumattn = newattn
    else:
        sumattn = [1.00] * len(L1.split(" "))    
    predictions = predictions[0]
    print(predictions)
    seen = set()
    seen_add = seen.add
    sentence = [quotapos(L2 + x.capitalize()[len(L2):], langspecs[langtolangid]['tgt']) + " " for x in predictions if not (x in seen or seen_add(x))]
    # sentence = [x.replace(L2, "") for x in sentence]
    sentence = '\n'.join(sentence)
    if langspecs[langtolangid]['provide_help'] and L2:
        sentence = quotapos(L2 + pred[0][0].capitalize()[len(L2):], langspecs[langtolangid]['tgt']) + '\n' + L2 + '\n' + sentence
    else:
        sentence = quotapos(L2 + pred[0][0].capitalize()[len(L2):], langspecs[langtolangid]['tgt']) + '\n' + sentence
    
    # print(scores)
    return JsonResponse({'result': sentence, 'attn': sumattn, 'partial': quotapos(L2)})



@login_required
def pushoutput(request):
    corpusops = json.loads(request.POST.get('ops'))
    request.session["corpusops"] = corpusops
    # keystroke = json.loads(request.POST.get('keys'))
    keytimeseries = json.loads(request.POST.get('keytimeseries'))

    translatedsets= translatedSet.objects.get(user=request.user, corpus=corpus.objects.get(pk=request.session["corpusid"]), langtolang=langtolang.objects.get(pk=request.session['langtolangid']))
    

    for i in range(len(corpusops)):
        translatedsent= translatedSentence.objects.get(translatedSet=translatedsets, src=corpusops[i][0].strip())
        translatedsent.tgt = corpusops[i][1]
        # keystrokes.objects.get_or_create(translatedSentence=translatedsent, atoz=0, space=0, **keystrokes[i])
        # print(keystrokes[i]["tab"])
        # keystrokesobj, created = keystrokes.objects.get_or_create(translatedSentence=translatedsent)
        # if created:
        #     keystrokesobj.atoz=0
        #     keystrokesobj.space=0
        #     print(keystroke[i])
        #     keystrokesobj.tab = keystroke[i]["tab"]
        #     keystrokesobj.enter = keystroke[i]["enter"]
        #     keystrokesobj.up = keystroke[i]["up"]
        #     keystrokesobj.down = keystroke[i]["down"]
        #     keystrokesobj.pgdn = keystroke[i]["pgdn"]
        #     keystrokesobj.pgup = keystroke[i]["pgup"]
        #     keystrokesobj.right = keystroke[i]["right"]
        #     keystrokesobj.left = keystroke[i]["left"]
        #     keystrokesobj.bkspc = keystroke[i]["bkspc"]
        #     keystrokesobj.end = keystroke[i]["end"]
        #     keystrokesobj.others = keystroke[i]["others"]
        #     time(translatedSentence=translatedsent, writetime=keystroke[i]["time"], thinktime=0).save()
        #     keystrokesobj.save()
        translatedsent.save()

    dockeystroke.objects.update_or_create(translatedSet=translatedsets, defaults={'keystrokeseries': keytimeseries, 'trump': 'Y'})
    # else:
    #     dockeystroke.objects.create(translatedSet=translatedsets, keystrokeseries=keytimeseries, trump='N')
    return HttpResponse('Success')

@login_required    
def getoutput(request):
    return JsonResponse({'result': request.session["corpusops"]})

@login_required
def end(request):
    if request.session["translatedsetid"] == 0:
        return redirect('/corpus')
    return render(request, 'end.html')