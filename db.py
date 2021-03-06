
'''
inspired from http://flask.pocoo.org/docs/0.12/patterns/sqlite3/
'''

from __future__ import print_function

import bisect
import sqlite3
import os
import copy
import logging

#logging.basicConfig(filename="error.log", level=logging.DEBUG)

DATABASE = 'annotation.db'

DATA_DIR_PATH = "data"

RAW_DATA_NAME = "raw.txt"
RAW_DATA_PATH = os.path.join(DATA_DIR_PATH, RAW_DATA_NAME)

WORD_LIST_NAME = "business_words.txt"
WORD_LIST_PATH = os.path.join(DATA_DIR_PATH, WORD_LIST_NAME)

ACTION_RECORD_NAME = "action.txt"
ACTION_RECORD_PATH = os.path.join(DATA_DIR_PATH, ACTION_RECORD_NAME)

# see http://stackoverflow.com/questions/2827623/python-create-object-and-add-attributes-to-it
# default object() has no `__dict__`, so can't set attr to it.
# following codes solves it
class ObjectWithDict(object):
    pass

_global_cached_data = ObjectWithDict()


def get_db():
    db = getattr(_global_cached_data, '_database', None)
    if db is None:
        db = _global_cached_data._database = sqlite3.connect(DATABASE)
    return db


def close_connection(exception):
    db = getattr(_global_cached_data, '_database', None)
    if db is not None:
        db.close()

def _escape_html(s, quote=False):
    '''
    copy from
    http://stackoverflow.com/questions/1061697/whats-the-easiest-way-to-escape-html-in-python
    Replace special characters "&", "<" and ">" to HTML-safe sequences.
    If the optional flag quote is true, the quotation mark character (")
    is also translated.
    '''
    s = s.replace(u"&", u"&amp;") # Must be done first!
    s = s.replace(u"<", u"&lt;")
    s = s.replace(u">", u"&gt;")
    if quote:
        s = s.replace(u'"', u"&quot;")
    return s

def _fragments_loader():
    fragment_list = []
    with open(RAW_DATA_PATH) as input_f:
        all_content = input_f.read()
        all_content = all_content.decode("utf-8").strip()
        all_content = _escape_html(all_content)
        parts = all_content.split(u"\n\n")
        for part in parts:
            fragment = part.split(u"\n")
            fragment_list.append(fragment)
    return fragment_list


def get_fragments():
    fragments = getattr(_global_cached_data, '_fragments', None)
    if fragments is None:
        print("LOAD!!-----")
        fragments = _global_cached_data._fragments = _fragments_loader()
    return fragments

def get_fragments_num():
    return len(get_fragments())

def get_certain_fragment(in_fragment_id):
    fragments = get_fragments()
    fragment_id = in_fragment_id
    if in_fragment_id < 0:
        fragment_id = 0
    elif in_fragment_id >= get_fragments_num():
        fragment_id = get_fragments_num() - 1
    fragment = fragments[fragment_id]
    return fragment, fragment_id


class Len2WordSet(object):
    def __init__(self):
        self._len2set = dict()
    
    def add_word(self, word):
        word_len = len(word)
        if word_len == 0:
            return False
        word_set = self._len2set.setdefault(word_len, set())
        word_set.add(word)
        return True

    def remove_word(self, word):
        word_len = len(word)
        if word_len == 0 or word_len not in self._len2set:
            return False
        word_set = self._len2set[word_len]
        #word_set.discard(word) # discard- no raise, remove raise error if no key
        if word in word_set:
            word_set.remove(word)
            return True
        else:
            return False

    def parse_from_file(self, word_file_path):
        '''
        parse from file
        '''
        with open(word_file_path) as input_f:
            for line in input_f:
                word = line.decode("utf-8").strip()
                self.add_word(word)

    def parse_from_word_list(self, word_list):
        '''
        parse form word list
        '''
        for word in word_list:
            self.add_word(word)

    def debug_output(self):
        '''
        debug output.
        '''
        for word_len in self._len2set:
            word_set = self._len2set[word_len]
            for word in word_set:
                print("{}, {}".format(word.encode("utf-8"), word_len))
   
    def __iter__(self):
        return self._len2set.__iter__()
    
    def __next__(self):
        return next(self.__iter__())

    def next(self):
        return self.__iter__().next()
    
    def __getitem__(self, idx):
        return self._len2set.__getitem__(idx)
    def __contains__(self, k):
        return self._len2set.__contains__(k)
    
    def setdefault(self, key, default):
        return self._len2set.setdefault(key, default)

    def keys(self):
        return self._len2set.keys()
    
    def items(self):
        return self._len2set.items()

def parse_base_word_set(base_word_set_path=WORD_LIST_PATH):
    base_word_set = set()
    with open(base_word_set_path) as bf:
        for line in bf:
            word = line.decode("utf-8").strip()
            if word == u"":
                continue
            base_word_set.add(word)
    return base_word_set

class AnnotationActionRecorder(object):
    ADD_ACTION = u"+"
    REMOVE_ACTION = u"-"
    def  __init__(self, action_fpath=ACTION_RECORD_PATH):
        self._action_fpath = action_fpath
        self._working_action_file = open(action_fpath, "at")
        self._action_cnt = 0
    
    def _append_action2file(self, word, action):
        if len(word) == 0:
            return False
        if isinstance(word, unicode):
            word = word.encode("utf-8")
        action = action.encode("utf-8")
        self._working_action_file.write("{}\t{}\t{}\n".format(
            self._action_cnt, word, action))
        self._working_action_file.flush()
        self._action_cnt += 1

    def add_word(self, word):
        '''
        append word to file
        '''
        return self._append_action2file(word, self.ADD_ACTION)

    def remove_word(self, word):
        '''
        append the removed file to removed file.
        '''
        return self._append_action2file(word, self.REMOVE_ACTION)

    def parse_action(self, base_word_set=None):
        '''
        parse action to get the result word list.
        '''
        word_set = copy.copy(base_word_set) if base_word_set else set()
        # 1. flush current working file
        self._working_action_file.flush()
        # 2. parse action
        with open(self._action_fpath) as af:
            for line in af:
                line_u = line.decode("utf-8").strip()
                if line_u == "":
                    continue
                cols = line_u.split(u"\t")
                #print(len(cols))
                if len(cols) != 3:
                    logging.getLogger(__name__).error(
                        "unknow format: {}".format(line)
                    )
                    continue
                word = cols[1]
                action = cols[2]
                if action == self.ADD_ACTION:
                    word_set.add(word)
                elif action == self.REMOVE_ACTION:
                    if word not in word_set:
                        logging.getLogger(__name__).error(("{} to be removed but "
                            "not in word set!").format(word.encode("utf-8")))
                    else:
                        word_set.remove(word)
                else:
                    logging.getLogger(__name__).error(("unknow action: "
                        "{}").format(action.encode("utf-8")))
        return list(word_set)

    def close(self):
        '''
        close handling.`
        '''
        logging.info("CLOSE action file!!!")
        self._working_action_file.close()

    def __del__(self):
        self.close()

class WordSource(object):
    ORIGIN = 0
    NEW = 1
    UNKNOWN = -1
    VALID_SOURCE = {ORIGIN, NEW}
    def __init__(self):
        self._word_source = {}

    def add_word_and_source(self, word, source):
        '''
        add word and source.
        if word has already been set source, nonting to do
        @return True when set, else False
        '''
        if source not in self.VALID_SOURCE:
            raise Exception("unkown source.")
        # if word has aleary been set source, don't change it!
        if word in self._word_source:
            return False
        self._word_source[word] = source
        return True
    
    def update_word_source(self, word, source):
        '''
        directly update the source
        '''
        self._word_source[word] = source
    
    def remove_word(self, word):
        '''
        delete the word.
        @return True if deleted, else False
        '''
        if word in self._word_source:
            del self._word_source[word]
            return True
        return False
    
    def get_word_source(self, word):
        '''
        get word source
        '''
        return self._word_source.get(word, self.UNKNOWN)


# def get_original_len2wordset():
#     len2wordset = getattr(_global_cached_data, "_origin_len2set", None)
#     if len2wordset is None:
#         len2wordset = _global_cached_data._origin_len2set = Len2WordSet()
#         recorder = get_action_recorder()
#         word_list = recorder.parse_action(WORD_LIST_PATH)
#         len2wordset.parse_from_word_list(word_list)
#     return len2wordset



# def get_new_len2wordset():
#     len2wordset = getattr(_global_cached_data, "_new_len2wordset", None)
#     if len2wordset is None:
#         len2wordset = _global_cached_data._new_len2wordset = Len2WordSet()
#     return len2wordset

# def add_new_word2len2wordset(word):
#     new_len2wordset = get_new_len2wordset()
#     word_len = len(word)
#     new_len2wordset.setdefault(word_len, set()).add(word)

def get_base_word_set():
    '''
    get base word set.
    '''
    base_word_set = getattr(_global_cached_data, "_base_word_set", None)
    if base_word_set is None:
        base_word_set = parse_base_word_set()
        setattr(_global_cached_data, "_base_word_set", base_word_set)
    return base_word_set

def get_action_recorder():
    '''
    get initialized action recoder.
    '''
    action_recorder = getattr(_global_cached_data, "_action_recorder", None)
    if action_recorder is None:
        action_recorder = AnnotationActionRecorder()
        setattr(_global_cached_data, "_action_recorder", action_recorder)
    return action_recorder

def close_action_recorder():
    '''
    close action recorder
    '''
    action_recorder = getattr(_global_cached_data, "_action_recorder", None)
    if action_recorder:
        action_recorder.close()

def get_len2word_set():
    '''
    get len2word set
    '''
    len2word_set = getattr(_global_cached_data, "_len2word_set", None)
    if len2word_set is None:
        len2word_set = _global_cached_data._len2word_set = Len2WordSet()
        recorder = get_action_recorder()
        base_word_set = get_base_word_set()
        all_word_list = recorder.parse_action(base_word_set) # to restore the previous tatus
        len2word_set.parse_from_word_list(all_word_list)
    return len2word_set

def _get_current_word_source_obj():
    word_source = getattr(_global_cached_data, "_word_source", None)
    if word_source is None:
        # init word source according to current word.
        word_source = WordSource()
        recorder = get_action_recorder()
        base_word_set = get_base_word_set()
        all_word_list = recorder.parse_action(base_word_set)
        for word in all_word_list:
            if word in base_word_set:
                source = WordSource.ORIGIN
            else:
                source = WordSource.NEW
            word_source.add_word_and_source(word, source)
        # bind to global data.
        setattr(_global_cached_data, "_word_source", word_source)
    return word_source

def get_word_source(word):
    return _get_current_word_source_obj().get_word_source(word)


def add_new_word_and_set_source_and_record(word):
    '''
    add new word to len2word_set and set it's source
    '''
    len2set = get_len2word_set()
    len2set.add_word(word)
    _get_current_word_source_obj().add_word_and_source(word, WordSource.NEW)
    get_action_recorder().add_word(word)

def remove_word_and_source_and_record(word):
    '''
    remove word from len2word and word's source from wordsource
    '''
    get_len2word_set().remove_word(word)
    _get_current_word_source_obj().remove_word(word)
    get_action_recorder().remove_word(word)


def forward_maximum_match(text, len2set):
    '''
    max-forward match, return match range, format is : [ (start_pos, end_pos), ... ]
    may be it could be improved!
    @return (word_range_list, matched_word_list)
    '''
    ascending_len_list = sorted(len2set.keys())
    pos = 0
    text_len = len(text)
    word_range_list = []
    matched_word_list = []
    while pos < text_len:
        left_len = text_len - pos
        # bisect.bisect(list, value)
        # return the index of the element which is the first that `bigger` than value
        # so the value at `index - 1` of list equals of less than value
        # do following logic, we get the valid sub-searching-length-list
        biggest_valid_len_index = bisect.bisect(ascending_len_list, left_len) - 1
        search_len_index = biggest_valid_len_index
        while search_len_index >= 0:
            # in descending length search
            word_len = ascending_len_list[search_len_index]
            token = text[pos: pos + word_len]
            wordset = len2set[word_len]
            if token in wordset:
                # found.
                word_range_list.append((pos, pos + word_len))
                matched_word_list.append(token)
                pos = pos + word_len
                break
            search_len_index -= 1
        else:
            # not found at this pos
            pos += 1
    return (word_range_list, matched_word_list)


def match_all_line_and_get_word2line_list(line_list, len2set):
    '''
    match multi-line, return dict {line_number: match_range},
    if not match for centain line, it will not occur in this dict.
    @return (match_result, word2line_list)
    '''
    multi_line_match_result = dict()
    word2line_list = dict()
    for line_num, line in enumerate(line_list):
        word_range_list, word_list = forward_maximum_match(line, len2set)
        multi_line_match_result[line_num] = word_range_list
        for word in word_list:
            line_list = word2line_list.setdefault(word, [])
            line_list.append(line_num)
    return (multi_line_match_result, word2line_list)

def match_some_line(all_line_list, to_match_line_num_list, len2set):
    '''
    only match some line.
    @return (match_result, word2line_list)
    '''
    match_result = dict()
    word2line_list = dict()
    for line_num in to_match_line_num_list:
        line = all_line_list[line_num]
        word_range_list, word_list = forward_maximum_match(line, len2set)
        # if word_range_list = []
        # it also should be assign!!
        match_result[line_num] = word_range_list
        for word in word_list:
            line_list = word2line_list.setdefault(word, [])
            line_list.append(line_num)
    return (match_result, word2line_list)

# def match_multi_line_with_multi_len2set(line_list, len2set_list):
#     '''
#     using multi-len2set to match multi-line
#     return dict: {line_numberm: match_range}, not line number if corresponding line not match
#     '''
#     match_result = dict()
#     for line_num, line in enumerate(line_list):
#         word_range_list = []
#         for len2set in len2set_list:
#             word_range_list.extend(forward_maximum_match(line, len2set))
#         if len(word_range_list) > 0:
#             # sort is needed!!
#             match_result[line_num] = sorted(word_range_list, key=lambda r: r[0])
#     return match_result


def _get_word2line_list():
    return getattr(_global_cached_data, "_current_word2line_list", None)

def set_current_word2line_list(word2line_list):
    '''
    set current word to line list.
    '''
    setattr(_global_cached_data, "_current_word2line_list", word2line_list)

def add_word2line_list(new_word2line_list):
    '''
    add new word to line list.
    '''
    word2line_list = _get_word2line_list()
    if word2line_list is None:
        logging.getLogger(__name__).error(
            "add_word2line_list error: None"
        )
        return 
    for word, line_list in new_word2line_list.items():
        if word not in word2line_list:
            word2line_list[word] = line_list
        else:
            word2line_list[word] = list(set(word2line_list[word] + line_list))



def remove_word2line_list(word):
    '''
    remove word
    '''
    word2line_list = _get_word2line_list()
    if word2line_list is None or word not in word2line_list:
        logging.getLogger(__name__).error(
            ("remove_word2line_list error: None or no word:"
            " {}").format(word.encoding("utf-8"))
        )
        return
    del word2line_list[word]

def get_word2line_list(word):
    '''
    get word to line list
    '''
    word2line_list = _get_word2line_list()
    if word2line_list is None or word not in word2line_list:
        logging.getLogger(__name__).error(
            ("get_word2line_list: None or no word: "
            "{}").format(word.encode("utf-8"))
        )
        return []
    return word2line_list[word]