# -*- coding: utf-8 -*-
"""
Test downloading scientific articles' infomration from the web.

Created on Sun Apr 19 20:46:55 2015

@author: alek
"""

import os, requests, re, difflib, time, numpy, subprocess, networkx, matplotlib.pyplot
import nltk, string, sklearn.metrics, sklearn.cluster
try:
    from selenium import webdriver
except ImportError:
    print "Install Selenium using sudo pip install selenium. If you aren't running Unix and can't use pip then you should abandon Windows."

from nltk.util import ngrams
import Article, GoogleScholarSearch

CACHE_DIR = '/home/alek/Desktop/cache' # Will store the page sources here.

scholarSearchEngine = GoogleScholarSearch.GoogleScholarSearchEngine() # Convenient to search through Google Scholar.

"""
    ---------------------------------------------------------------------------
    PLOT FORMATTING.
    ---------------------------------------------------------------------------
"""
ticksFontSize = 18
ticksFontSizeSmall = 16
labelsFontSizeSmall = 24
labelsFontSize = 30
titleFontSize = 34
graphLabelFontSize=8

legendFontSize = 16
legendFontSizeSmall =14

cm = matplotlib.pyplot.cm.get_cmap('jet')

matplotlib.rc('xtick', labelsize=ticksFontSize)
matplotlib.rc('ytick', labelsize=ticksFontSize)

"""
    ---------------------------------------------------------------------------
    REGEXES.
    ---------------------------------------------------------------------------
"""
" General regexes. "
IntegersParern = re.compile("\d+") # Any integer.
YearPattern = re.compile('\([0-9a-zA-Z\s]*\d{4}\)') # Any four-digit year encolsed in parentheses; may be preceded by a month in any format and also a day.
LinksPattern = re.compile('"((http|ftp)s?://.*?)"') # Will find URLs in a website text.

" CiteULike.org-specific regexes. "
TitlePattern = re.compile(';</span>.+</a></h2>') # A number of regexes designed to extract bits of information from the lines of CiteULike.org results website.
JournalPattern = re.compile('<i>[a-zA-Z\s\W\d]+</i>')
NoPattern = re.compile("No\.\s\d+")
VolPattern = re.compile("Vol\.\s\d+")
DOIPattern = re.compile(">doi\:[\W\w]+</a></div>")
AuthorPattern = re.compile('>[a-zA-Z\s.-]+</a>')
TagPattern = re.compile('>[a-zA-Z]+</a>')
ArticleIDsPattern = re.compile('<tr class="list {article_id:\d+}" data-article_id=\d+>') # Will find the beginnings of the articles from CIteULike.org.

" Google Scholar-specific regexes. "
CitedByPattern = re.compile('cites=\d+') # Will find those parts of the links that enable the papers that cite a given article to be displayed on Google Scholar.
TitlePatternGoogle = re.compile('nossl=1">[\s\w\d\:\-\,\.\;\&\#]+</a></h3>') # Just think of all the stuff people might put in titles... Also sometimes Google will put weird stuff like &#8208; instead of -, which probably has to do with encoding. But I know too little about this to fix it.
YearPatternGoogle = re.compile('\,\s\d{4}[\s\-<]*')
ArticleInfoPatternGoogle = re.compile('[\.\,\-\s\w]+\,\s\d{4}[\s\-<]*') # Will find the list of authors, journal, and year.
CitedByNumberPattern = re.compile('Cited\sby\s\d+') # How many times the given article has been cited.

def getArticlesCiteULike(authors=[], keywords=[], yearStart=1800, yearEnd=3000, title="", isbn="none", pageLimit=2):
    """ Find scientific articles that match given criteria on-line.
    
    Arguments
    ----------
    authors - list of strings with author names; can be surnames or surnames with
        names or initials.
    keywords - list of strings with the keywords to look for.
    yearStart - starting year of the published year bracket within which to find
        the articles.
    yearEnd - fina; year of the published year bracket within which to find
        the articles.
    title - string with the title of the article.
    isbn - str with the ISBN of the publication.
    pageLimit - int, how many pages of the results will be searched.
        
    Returns
    ----------
    A list of Articles @see Article.
    """
    pageNo = 1 # Number of the page with results.
    
    " Go through all the result pages we might get. "
    while pageNo <= pageLimit: # Unlikely that we'll get so many results but we don't want infinite loops, do we?
        " Build the search URL. "
        if not title: # We aren't looking for a specific title.
            BASE_SEARCH_URL = "http://www.citeulike.org/search/all/page/{}?q=".format( pageNo ) # All the search criteria are appended to this.
            searchURL = BASE_SEARCH_URL # Start from this and add all the search criteria.
            for tag in keywords:
                searchURL += "tag%3A"
                searchURL += '"{}"'.format(tag)
                searchURL += "+"
            for author in authors:
                searchURL += "author%3A"
                searchURL += '"{}"'.format(author) # author has to be in quotes.
                searchURL += "+"
            searchURL += "year%3A%5B{}+TO+{}%5D".format(yearStart,yearEnd)
            searchURL += "+isbn%3A{}".format(isbn)
        else: # The URL to look for specific titles is a bit different.
            BASE_SEARCH_URL = "http://www.citeulike.org/search/all/page/{}?q=title>".format( pageNo )
            searchURL = BASE_SEARCH_URL # Start from this and add all the search criteria.
            searchURL += title + "+"
            for tag in keywords:
                searchURL += "tag%3A"
                searchURL += '"{}"'.format(tag)
                searchURL += "+"
            for author in authors:
                searchURL += "author%3A"
                searchURL += '"{}"'.format(author) # author has to be in quotes.
                searchURL += "+"
            searchURL += "year%3A%5B{}+TO+{}%5D".format(yearStart,yearEnd)
            searchURL += "+isbn%3A{}".format(isbn)

        " Perform the actual search. "
        the_page = requests.get(searchURL).text # Get the text version of the website. Use requests not urllib2 because the page will be too large for it.
        
        lines = the_page.split("\n") # Parsing lines is easier than coming up with regexes to get the info about all the articles from the_page. Besides not every article will have all the information.
        
        # Initialise the artcile attributes.
        articleID=-1; articleTitle=""; authors=[]; year=0; journalTitle=""; doi=""; volume=-1; number=-1; tags=[]; abstract="";
        articles = [] # Articles we've found.
        firstArticle = True # If this is the first article we're reading.
        for i in range(len(lines)):
            if lines[i].startswith('<tr class="list {article_id:'):
                if firstArticle: # articleID and all the rest aren't defined yet.
                    articleID = int(IntegersParern.findall(lines[i])[0])
                    firstArticle = False
                else: # First add the artcile we've just parsed, then proceed to parsing the new one.
                    articles.append( Article.Article(articleID, articleTitle, authors, year, journalTitle, doi, volume, number, tags, abstract) )
                    articleID = int(IntegersParern.findall(lines[i])[0])
            if '<a class="title"' in lines[i]:
                articleTitle = TitlePattern.findall(lines[i])[0].rstrip("</a></h2>").lstrip(";</span>")
            if "<a href='http://dx.doi.org" in lines[i]:
                try:
                    journalTitle = JournalPattern.findall(lines[i])[0].rstrip("</i>").lstrip("<i>")
                except IndexError:
                    print "\nNo journalTitle for:\n\t{}".format(lines[i])
                    journalTitle = "UNKNOWN JOURNAL"
                    
                try:
                    year = int( YearPattern.findall(lines[i])[0][-5:-1] ) # This may have a day and month in front, only extract the year (always last and followed by ")" ).
                except IndexError:
                    print "\nNo year for:\n\t{}".format(lines[i])
                    year = 0
                
                try:
                    volume = int(VolPattern.findall(lines[i])[0].lstrip("Vol. "))
                except IndexError:
                    print "\nNo volume for:\n\t{}".format(lines[i])
                    volume = -1
                
                try:
                    number = int(NoPattern.findall(lines[i])[0].lstrip("No. "))
                except (IndexError, ValueError):
                    print "\nNo number for:\n\t{}".format(lines[i])
                    number = -1
                
                doi = DOIPattern.findall(lines[i])[0].lstrip(">").rstrip("</a></div>")
            if '<a class="author"' in lines[i]:
                authors = map(lambda x: x.lstrip(">").rstrip("</a>"), AuthorPattern.findall(lines[i]))
            if '<span class="taglist">' in lines[i]:
                tags = map(lambda x: x.lstrip(">").rstrip("</a>"), TagPattern.findall(lines[i]))
            if '<h3>Abstract</h3>' in lines[i]:
                abstract = lines[i+1].lstrip("<p>").rstrip("</p>")
        # Add the last article.
        articles.append( Article.Article(articleTitle, authors, year, journalTitle, doi, volume, number, tags, abstract, articleID) )

        pageNo += 1 # Go to the next results page.
        
    return articles

def getSourceWithFirefox(url, cacheName=None):
    """ Get the string with the source of the website at the URL. If desired,
    will cache the source in a text file.
    
    Argumets
    ----------
    url - str with a full URL of a website
    cacheName - None or str, if is type str will be the name of the text file
        where the source is going to be saved.
        
    Returns
    ----------
    str with the source of the website.
    """
    firefoxDriver = webdriver.Firefox() # Open Firefox.
    
    firefoxDriver.get(url) # Go to the page.
    src = firefoxDriver.page_source # Get source because.
    
    firefoxDriver.close()
    
    return src

def getArticlesFromSource(source, searchTerms):
    """ Parses a given Google Scholar results page and returns a list of 
        Articles that are displayed there. This can be used to find citing or 
        related Articles using the citingArticlesURL or relatedArticlesURL fields.
        
        Returns a list of Artciles. Each Article contains the information related
        itin the following fields that every Article has:
            Title    : str, title of the publication
            Authors  : list of strings with author names (example: DF Easton, DT Bishop, D Ford)
            Journal  : str, name of the journal (example: Nature, Cancer Research)
            Year     : str, journal name & year (example: Nature, 2001)
            Keywords : list of strings with search terms used in the query
            Abstract : str, abstract of the publication
            
        Additional fields are added when creating the Articles here:
            JournalURL  : string with a link to the journal main website (example: www.nature.com),
                "Unavailable" if journal's URL is unkown.
            fullURL     : string with a link to the full text in HTML/PDF format,
                "Unavailable" if full text is unavailable
            pubURL      : string with a link to the publicly available version of the paper
            citingArticlesURL : string with a link to the site with articles citing this one
            relatedArticlesURL: string with a link to the site with articles related this one
                according to Google Scholar
            pubNoCitations    : number of times the publication is cited
            

        Arguments
        ----------
        @param source - ASCII str, HTML source of the page from which to extract the Articles.
        @param searchTerms - list of strings that we'll search for.
        
        Returns
        ----------
        @return List of Articles (@see Article.Article), or an empty list if
            nothing is found.
    """
    soup = GoogleScholarSearch.BeautifulSoup(source, "lxml")
    results = [] # Store the articles here.
    
    for record in soup.find_all('div',{'class': 'gs_r'}):#soup('p', {'class': 'g'}):
        allAs = record.find_all('a') # All <a></a> fields corresponding to this article.

        " Get the public URL and the title, maybe full text URL if we're lucky. "
        if "[CITATION]" in record.text: # The 'old fashioned way' works for citations.
            pubTitle=record.find('div',{'class': 'gs_ri'}).find('h3',{'class': 'gs_rt'}).get_text().lstrip('[CITATION][C]')
            if len( allAs[0].find_all("span") ): # The first <a> has some <span> children.
                fullURL = allAs[0].attrs['href'] # URL to the full text in HTML or PDF format (typically).
                pubURL = allAs[1].attrs['href'] # This will be the public URL one gets when they click on the title.
#                pubTitle = allAs[1].text # Public URL has the title of the article as text.
            else: # The first <a> of the result is the one with the title and public URL.
                fullURL = "Unavailable" # No full text for this article... :(
                pubURL = allAs[0].attrs['href']
#                pubTitle = allAs[0].text
        else: # This is a neater way, but doens't work for citations
            titleURLPart=record.find('div',{'class': 'gs_ri'}).find('h3',{'class': 'gs_rt'})
            pubURL=titleURLPart.find('a').get('href')
            pubTitle=titleURLPart.find('a').get_text()
        
            if len( allAs[0].find_all("span") ): # The first <a> has some <span> children.
                fullURL = allAs[0].attrs['href'] # URL to the full text in HTML or PDF format (typically).
            else: # The first <a> of the result is the one with the title and public URL.
                fullURL = "Unavailable" # No full text for this article... :(

        " Get the articles citing and related to this one. "
        citingArticlesURL = "UNKNOWN" # Initialise in case something goes wrong in parsing and this will be undefined.
        relatedArticlesURL = "UNKNOWN"#TODO these won't always be found, why?
        pubNoCitations = 0
        for a in allAs:
            if "Cited by" in a.text:
                pubNoCitations = int(  GoogleScholarSearch.IntegerPattern.findall(a.text)[0] )
                citingArticlesURL = a.attrs['href'] # Articles that cite this one.
            elif "Related articles" in a.text:
                relatedArticlesURL = a.attrs['href'] # URL to the related articles.
        
        " Get the authors; they're displayed in green, use it. "
        authorPart = record.find('div',attrs={'class':'gs_a'}).text #record.first('font', {'color': 'green'}).string
        if authorPart is None:    
            authorPart = ''
            # Sometimes even BeautifulSoup can fail, fall back to regex.
            m = re.findall('<font color="green">(.*)</font>', str(record))
            if len(m)>0:
                authorPart = m[0]

        " Get journal name, publication year, and authors' list. "
        # Assume that the fields are delimited by ' - ', the first entry will be the
        # list of authors, the last entry is the journal URL. We also have journal name and year there.
        try: # Sometimes there simply is no year associated to some entires.
            pubJournalYear = int(GoogleScholarSearch.IntegerPattern.findall(authorPart)[0]) # We might get other integers, but not preceded by whitespaces.
        except IndexError: # Not much I can do about it...
            pubJournalYear=9999
        
        idx_start = authorPart.find(' - ') # Here the authors' list ends.
        idx_end = authorPart.rfind(' - ') # Here the journal's public URL starts.
        idx_jrnlNameEnd = authorPart.rfind(',') # After the journal name.
        
        pubJournalName = authorPart[idx_start:idx_jrnlNameEnd].lstrip().lstrip("-")
        
        pubAuthors = authorPart[:idx_start]                
        pubJournalURL = authorPart[idx_end + 3:]
        # If (only one ' - ' is found) and (the end bit contains '\d\d\d\d')
        # then the last bit is journal year instead of journal URL
        if pubJournalYear=='' and re.search('\d\d\d\d', pubJournalURL)!=None:
            pubJournalYear = pubJournalURL
            pubJournalURL = 'Unavailable'
        
        " Get the abstract. "
        abstractDiv = record.find('div',attrs={'class':'gs_rs'}) # Abstract info sits here.
        if not abstractDiv is None:
            pubAbstract = abstractDiv.text
        else: # Sometimes there simply is no abstract.
            pubAbstract = "Abstract unavailable" # Can't conjure it.
        
        " Save the results. "
        results.append( Article.Article(pubTitle.encode('utf-8'),map(lambda x: x.encode('utf-8'),pubAuthors.split(',')),pubJournalYear,pubJournalName.encode('utf-8'),tagList=searchTerms,abstract=pubAbstract.encode('utf-8')) )
        # All the URLs.
        results[-1].fullURL = fullURL
        results[-1].pubURL = pubURL
        results[-1].citingArticlesURL = citingArticlesURL
        results[-1].relatedArticlesURL = relatedArticlesURL
        # This might be useful to something, e.g. seeing whcih publications have the most impact.
        results[-1].pubNoCitations = pubNoCitations
            
    return results # If everything's gone smoothly...

def getCitingArticles(targetArticle,cacheDir,trim=None):
    """ Get all the articles citing an Article. Try to use cached websites
    and cache them on the way.
    
    Arguments
    ----------
    targetArticle - and instance of an Article, will get the Articles
        that cite it.
    cacheDir - string with the directory where the source of the parsed sites
        will be saved to and read from.
    trim - int or None, whether to limit the number of Articles that will be
        retrieved and to how many. If None, all the Articles will be retrieved.
    
    Returns
    ----------
    A list of Articles.
    """
    citingArticles = [] # Collect citing articles from all the result pages.
    citingArticlesURLParts = targetArticle.citingArticlesURL.split("?") # Need to split this to be able to display different result pages.

    # Can only display 50 pages with 20 results per page - might not be ableto get all citations.
    if trim is None:
        noArticlesInSearch=min(50*20,targetArticle.pubNoCitations)
    else: # For completness' sake, see if trim is definitely smaller than available no. citations.
        noArticlesInSearch=min(50*20,targetArticle.pubNoCitations,trim)
    
    for startArticleIndex in range(0,noArticlesInSearch,20): # The first article to be displayed on the Scholar page. Go every 20 articles to limit the number of requests we send.
        url = "https://scholar.google.com"+citingArticlesURLParts[0]+"?"+\
            "start={}&num=20&".format(startArticleIndex)+\
            citingArticlesURLParts[1].replace("as_sdt=2005","as_sdt=0,5")# as_sdt=0,5 should only return articles, but it returns everything?

        try: # Try to get the cached source in the first instance.
            with open(os.path.join(cacheDir,url.lstrip('https://scholar.google.com/scholar?')),"r") as cacheFile:
                src=cacheFile.read()
                temp = getArticlesFromSource(src,targetArticle.Keywords)
        except IOError: # No cache file - retrieve source with Firefox.
            src = getSourceWithFirefox(url) # Get the source of the website.
            src = src.encode('ascii', 'ignore') # Convert src from unicode to something, which can be written to a file.
            temp = getArticlesFromSource(src,targetArticle.Keywords)
            if not "Please show you\'re not a robot" in src and not len(temp)==0: # Don't cache robot verification or empty pages.
                with open(os.path.join(cacheDir,url.lstrip('https://scholar.google.com/scholar?')),"w") as cacheFile:
                    cacheFile.write(src)
                    dt = 60+numpy.random.randint(0,60,1)[0]
                    print "\tSleeping for {} seconds.".format(dt)
                    time.sleep(dt) # Wait a while to not send requests too quickly
            
        if not "Please show you\'re not a robot" in src: # Searching still works - get the citing articles.
            citingArticles.extend(temp) # Add articles from this page to the results.
            print "Start IDX: {}, no. articles: {}".format(startArticleIndex,len(temp))

        else: # Require manual intervention to show I'm not a robot.
            # Use the webdriver; doing it through browsers doesn't work.
            firefoxDriver = webdriver.Firefox()
            firefoxDriver.get(url)
            # Let the user know they have to convince Google they're a human.
            proc = subprocess.Popen(['zenity', '--info', '--text=Please show Google that you are not a robot and click OK to continue downloading articles.\n\nTry to change VPN as well.'])
            proc.wait() # Wait for the user to click OK having shown that they're human.
            src = firefoxDriver.page_source # Get the source with the check passed (actual articles are here).
            firefoxDriver.close()
            
            # Get the actual source of the website for this batch of articles , cache it and retrieve Articles from it.
            src = src.encode('ascii', 'ignore')
            with open(os.path.join(cacheDir,url.lstrip('https://scholar.google.com/scholar?')),"w") as cacheFile:
                cacheFile.write(src)
            temp = getArticlesFromSource(src,targetArticle.Keywords)
            print "Start IDX: {}, no. articles: {}".format(startArticleIndex,len(temp))
            citingArticles.extend(temp)
    
    if trim is None: # Return all the Articles.
        return citingArticles
    else: # if trim<20 we got all the 20 articles from the first page of results.
        return citingArticles[:trim]

def findArticle(targetArticle):
    """ Find an Article on Google Scholar that resembles the input Article
    instance.
    
    Arguments
    ----------
    An instance of an Article that has as many fields filled in as possible.
        Will use the Year, Title and Authors attributes to find this Article
        on Googgle.
    
    Returns
    ----------
    An instance of Article.
    
    Raises
    ----------
    RuntimeError if cannot access Google due to catpcha restrictions.
    """
    # Get all the articles from the page when we look for the title of theArticle of interest.
    # as_sdt=0,5 should only return articles, but it returns everything?
    searchURL = "/scholar?hl=en&as_sdt=0,5&q=" # Now we're searching for articles only (as_sdt=0,5).
    searchURL += targetArticle.Title.replace(" ","%20") # Search by title. We can't have space in there.
    try: # Sometimes captcha might kick in here.
        papers = scholarSearchEngine.getArticlesFromPage(searchURL, ["Mock","terms"])
    except RuntimeError as rntmeerr:
        if "Please show you&#39;re not a robot" in rntmeerr.message:
            raise RuntimeError("Cannot find the base article due to captcha restriction.")
        else: # No idea what happened, print the whole source of the site.
            raise rntmeerr    
    if len(papers)==0:
        raise RuntimeError("Cannot find the base article due to captcha restriction.")
    
    # Find targetArticle from the many that will be displayed - will define articleID.
    articleID = 0 # Which article from the page is the one we're looking for.
    currentMaxCited = 0
    currentHighestAuthorSimilarity = 0
    for i in range(len(papers)): # Articles that we have to look at to match to the article.
        if targetArticle.Year==papers[i].Year: # This article is from the same year, promising.
            if difflib.SequenceMatcher(a="".join(targetArticle.Authors).lower(), b="".join(papers[i].Authors).lower()).ratio() > currentHighestAuthorSimilarity: # The authors of this article look more like the authors of the input article.
                currentHighestAuthorSimilarity = difflib.SequenceMatcher(a="".join(targetArticle.Authors).lower(), b="".join(papers[i].Authors).lower()).ratio()
                if papers[i].pubNoCitations> currentMaxCited: # We're probably after the popular articles. Sometimes will get copies of the original article with fewer citations.
                    articleID = i # This is probably targetArticle we're after.
    print "Found article:\n{}\n when looking for:\n{}.".format(papers[articleID],targetArticle)
    return papers[articleID]

def addCitingArticlesToNetwork(allArticles,targetIdx,network,trim=None):
    """ Find Articles citing one of all the Articles. Add the corresponding 
    edges to the netwrokx DiGraph.
    
    Attributes
    ----------
    allArticles - a list of Articles; will extend it with the Articles citing
        the target Article.
    targetIdx - int, index of input allArticles, will find the Articles citing
        this Article.
    network - networkx.classes.digraph.DiGraph to which the edges, corresponding
        to the citation of target Article, will be added.
    trim - int or None, how many citing articles to keep, will keep all of them
        if trim is None. Will keep the first trim citing articles that are retreived.
    """
    citingArticlesTemp=getCitingArticles(allArticles[targetIdx],CACHE_DIR,trim) # These articles cite the target Article
    
    citingArticles=[] # The citing articles without the ones already in allArticles.
    citingIndices=[] # Indices of allArticles that cite targetIdx article.
    for tempArt in citingArticlesTemp:
        if tempArt in allArticles:
            citingIndices.append(allArticles.index(tempArt))
        else:
            citingArticles.append(tempArt)
    
    if not trim is None: # Trim the citing articles if desired.
        citingArticles=citingArticles[:trim]
        
    # Add edges between the target article and the exisitng allArticles.
    network.add_edges_from([(targetIdx,i) for i in citingIndices])
    
    # First add the edges to the citingArticless - need to have unchanged allArticles here.
    # Account for the fact that we'll extend allArticles with the citingArticles (+len(allArticles)).
    network.add_edges_from([(targetIdx,i+len(allArticles)) for i in range(len(citingArticles))])
    
    allArticles.extend(citingArticles) # Record these here.

def findNGrams(tokens,lengths=[2,3,4,5]):
    """ Given an iterable of tokens (a sequence of words and punctuation
    find all N-grams of chosen lengths in those.
    
    Arguments
    ----------
    tokens - list of strings with words.
    lengths - list of ints with lengths of the N-grams that will be found.
    
    Returns
    ----------
    2-tuple containing:
        * list of strings with N-grams
        * list of ints with corresponding occurence counts
    """
    combinedGrams=[] # N-grams put together into single string tokens, not tuples of individual tokens.
    
    for length in lengths:
        grams=ngrams(tokens, length)
        for gram in grams:
            # Combine the N-gram into a string (it's a tuple of words).
            combinedGrams.append("".join([" "+str(g) if not g.startswith("'") and 
                g not in string.punctuation else g for g in gram]).strip())
    
    fdist=nltk.FreqDist(combinedGrams)
    return combinedGrams,fdist.values()

def getArticleKeywords(articles, maxLength=3):
    """ Parse titles of a number of articles and extract keywords that occur
    in them. A keyword is defined as a grouping of several words, with punctuation
    and stopwords (*nltk.corpus.stopwords.words('english')*) removed. Will 
    also add keywords from every input Article into the corresponding entry
    in articles list.
    
    Arguments
    ----------
    articles - a list of Articles.
    maxLength - int, the largest number of tokens per keyword.
    
    Returns
    ----------
    2-tuple with numpy.ndarrays of shape (len(articles),) with
        * strings of keywords
        * ints with the number of occurrences of the given keyword in all titles
    
    Example
    ----------
    "A general theory of the plasma of an arc" would return keywords:
        ['A', 'general', 'theory', 'of', 'the', 'plasma', 'of', 'an', 'arc',
        'A general', 'general theory', 'theory of', 'of the', 'the plasma',
        'plasma of', 'of an', 'an arc', 'A general theory', 'general theory of',
        'theory of the', 'of the plasma', 'the plasma of', 'plasma of an', 'of an arc']
    Out of these, ['A','of','the','an','of the','of an'] would be filtered out.
    """
    
    # Identify keywords.
    tokens=[]
    for title in [art.Title for art in articles]:
        tokens.extend(nltk.wordpunct_tokenize(title))
    
    # Filter out meaningless words and punctuation.
    tokens=filter(lambda s: not s.lower() in nltk.corpus.stopwords.words('english') and
        not s in string.punctuation, tokens)

    # Find keywords (length 1, 2, or 3) and how often they occur in all the titles.
    keywords,frequencies=findNGrams(tokens,lengths=range(1,maxLength+1))
    keywords=numpy.array(keywords)
    frequencies=numpy.array(frequencies)
    sortedIndices=frequencies.argsort()[::-1] # Go in descending order of frequencies.
    frequencies=frequencies[sortedIndices]
    keywords=keywords[sortedIndices]

    # Assign keywords to Articles.
    for i in range(len(articles)):
        artTitleTokens=nltk.wordpunct_tokenize(articles[i].Title) # The tokens of this article's title.
        # Filter out meaningless words and punctuation.
        artTitleTokens=filter(lambda s: not s.lower() in nltk.corpus.stopwords.words('english') and
            not s in string.punctuation, artTitleTokens)
        
        # Use the same algorithm but for this article only.
        artKeywords,artFreq=findNGrams(artTitleTokens,lengths=[1,2,3])
        articles[i].Keywords=artKeywords
    
    return keywords,frequencies

def collectArticleFeatures(articles,keywords):
    """ Given a list of articles and the desired keywords, find which keywords
    appear in which article. Build a matrix that reflects this.
    
    Arguments
    ----------
    articles - a list of articles of len N with Articles, which had their keyword
        fields filled.
    keywords - a list of length K with keyword strings that will be identified
        in the articles' titles.
    
    Returns
    ----------
    numpy.ndarray of shape(N,K), dtype=bool with 1s where a given keyword 
        appears in the Article's title, 0s otherwise. Each row corresponds
        to an Article, column to a keyword.
    """
    # See which keywords appear in which article.
    articleFeatures=numpy.zeros((len(articles),len(keywords)),dtype=bool)
    for i in range(len(articles)):
        for j in range(len(keywords)):
            if keywords[j] in articles[i].Keywords:
                articleFeatures[i,j]=True # This keywords appears, if not leave artcileFeatures at 0.
    
    return articleFeatures

if __name__=="__main__": # If this is run as a stand-alone script run the verification/example searches.
    " Example search for many articles following search terms. "
#    authors = ["langmuir", "tonks"] # Author names.
#    tags = ["langmuir", "probe"] # Tags we want to look for.
#    years = (1900,2015) # Year brackets we're interested in.
#    isbn = "none"
#    articles = getArticlesCiteULike(authors, tags, years[0], years[1], isbn) # One way, seems to be more restrictive because we can specify additional criteria, like min and max year etc.
#    article = scholarSearchEngine.search(tags) # Another way, also works.

    " Search for the desired article. "
    theArticle = Article.Article("The Theory of Collectors in Gaseous Discharges", ["H.M. Mott-Smith", "Irving Langmuir"], 1926, "Physical Review", doi="10.1103/physrev.28.727", volume=28, number=4, citeULikeID=2534514) # The desired article.
    theFoundArticle=findArticle(theArticle)
    allArticles=[theFoundArticle] # This Article and all the ones that cite it.
    G = networkx.DiGraph()
    
    # Find articles citing theFoundArticle. It's a popular one so only retian some of the ones that cite it.
    addCitingArticlesToNetwork(allArticles,0, G, trim=10)
    # Add more citing articles into the network.
    addCitingArticlesToNetwork(allArticles,3, G, trim=10)
    addCitingArticlesToNetwork(allArticles,4, G, trim=10)
    addCitingArticlesToNetwork(allArticles,21, G, trim=10)
    
    """
        --------------------------------------------------------------------
        Plot the network of who cites whom. 
        --------------------------------------------------------------------
    """
    noCitations = [art.pubNoCitations for art in allArticles] # Colour the nodes by no. citations they have.
    
    # X axis is the publication year, Y is the index of the Article.
#    poses = dict(zip(range(len(allArticles)),[(allArticles[i].Year,i) for i in range(len(allArticles))]))
    poses = networkx.spring_layout(G) # Cleaner to look at but less information. Might also want to use shell_layout
    
    # Plot the network of which article cites which.
    fig, ax = matplotlib.pyplot.subplots(1,figsize=(12,8))
    matplotlib.pyplot.grid(linewidth=2)
    ax.tick_params(axis='both',reset=False,which='both',length=5,width=1.5)
#    ax.set_xlabel(r'$Publication\ year$',fontsize=labelsFontSize)
#    ax.set_ylabel(r'$Article\ index$',fontsize=labelsFontSize)
#    ax.set_xlim(1900,2016)
#    ax.set_ylim(-0.5,len(allArticles)+0.5)
    matplotlib.pyplot.subplots_adjust(left=0.1, right=1, top=0.95, bottom=0.1)
    
    nodePatches=networkx.draw_networkx_nodes(G, poses, cmap=matplotlib.pyplot.get_cmap('jet'), node_color=noCitations, ax=ax)
    networkx.draw_networkx_edges(G, poses, edge_color='k', arrows=True, ax=ax)
    #    networkx.draw_networkx_labels(G, poses, dict(zip(range(len(allArticles)),[art.Title for art in allArticles])), font_size=labelsFontSize, ax=ax)
    
    # Add a colourbar to show the number of citations.
    nodePatches.set_clim(0,max(noCitations))
    cbar=fig.colorbar(nodePatches,ticks=numpy.linspace(0,max(noCitations),10),pad=0.01)
    cbarBox=cbar.ax.get_position()
    cbar.ax.set_position([cbarBox.x0, cbarBox.y0+cbarBox.height * 0.12, cbarBox.width*1., cbarBox.height * 0.75])
    cbar.ax.set_ylabel(r'$No.\ citations$', size=labelsFontSize)
    cbar.set_clim(0,max(noCitations))
    
    fig.show()
    
    """
        --------------------------------------------------------------------
        Plot a network showing who cites whom and the keywords of the Articles.
        --------------------------------------------------------------------
    """
    " Extract keywords from Articles' titles. "
    keywords,frequencies=getArticleKeywords(allArticles, maxLength=3)
    
    # Trim to only keep the keywords that appear more than once.
    keywords=keywords[numpy.where(frequencies>1)]
    keywordIndices=range(keywords.size) # Need numerical values corresponding to every keyword.
    frequencies=frequencies[numpy.where(frequencies>1)]
    
    # Build a matrix to look for clusters of articles with similar keywords.
    articleFeatures=collectArticleFeatures(allArticles,keywords)

    " Use sklearn to find no. clusters and which article belongs to which cluster. "
    clusterSizes=range(2,4) # Try a few different cluster sizes.
    scores=[] # Corresponding slihouette scores.
    for n_clusters in clusterSizes:
        clusterer = sklearn.cluster.KMeans(n_clusters=n_clusters)
        cluster_labels = clusterer.fit_predict(articleFeatures)
        # The silhouette_score gives the average value for all the samples.
        # This gives a perspective into the density and separation of the formed clusters.
        silhouette_avg = sklearn.metrics.silhouette_score(articleFeatures, cluster_labels)
        print("For n_clusters =", n_clusters,"The average silhouette_score is :", silhouette_avg)
        scores.append(silhouette_avg)
    
    # Use the best no. clusters.
    clusterer=sklearn.cluster.KMeans(n_clusters=clusterSizes[scores.index(max(scores))])
    cluster_labels=clusterer.fit_predict(articleFeatures)

    " Histogram of keywords. "
    fig, ax = matplotlib.pyplot.subplots(1,figsize=(12,8))
    matplotlib.pyplot.grid(linewidth=2)
    ax.tick_params(axis='both',reset=False,which='both',length=5,width=1.5)
    ax.set_xlabel(r'$Keyword$',fontsize=labelsFontSize)
    ax.set_ylabel(r'$Frequency$',fontsize=labelsFontSize)
    matplotlib.pyplot.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)
    bins = numpy.arange(0,max(frequencies)+1,1)
    ax.bar(range(frequencies.size), frequencies, 0.5, color='k')
    ax.set_xticklabels(keywords,rotation=45,fontsize=ticksFontSizeSmall)
    ax.set_ylim(0,max(frequencies)+1)
    box=ax.get_position()
    ax.set_position([box.x0, box.y0+box.height*0.3, box.width, box.height*0.7])
    fig.show()

    " Dirgraph showing clusters of keywords, no citations as size, and citations as arrows. "
    poses=networkx.graphviz_layout(G)
    
    # Plot the network of which article cites which and what keywords they have.
    fig, ax = matplotlib.pyplot.subplots(1,figsize=(12,8))
    matplotlib.pyplot.grid(linewidth=2)
    ax.tick_params(axis='both',reset=False,which='both',length=5,width=1.5)
    matplotlib.pyplot.subplots_adjust(left=0.1, right=1, top=0.95, bottom=0.1)
    
    nodePatches=networkx.draw_networkx_nodes(G, poses, cmap=matplotlib.pyplot.get_cmap('jet'), node_color=cluster_labels, node_size=noCitations, ax=ax)
    networkx.draw_networkx_edges(G, poses, edge_color='k', arrows=True, ax=ax)
    
    # Draw keywords of every Article.
    networkx.draw_networkx_labels(G, poses, dict(zip(range(len(allArticles)),[keywords[articleFeatures[i,:]] for i in range(len(allArticles))])), font_size=graphLabelFontSize, ax=ax)
    
    # Add a colourbar
    nodePatches.set_clim(0,max(cluster_labels))
    cbar=fig.colorbar(nodePatches,ticks=numpy.arange(0,max(cluster_labels)+1,2),pad=0.01)
    cbarBox=cbar.ax.get_position()
    cbar.ax.set_position([cbarBox.x0, cbarBox.y0+cbarBox.height * 0.12, cbarBox.width*1., cbarBox.height * 0.75])
    cbar.ax.set_ylabel(r'$Cluster\ ID$', size=labelsFontSize)
    cbar.set_clim(0,max(cluster_labels))
    
    fig.show()