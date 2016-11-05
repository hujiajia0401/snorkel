import sys
import os

# from templates import *
from lf_helpers import *
from utils import get_as_dict
from table_utils import min_row_diff, min_col_diff, num_rows, num_cols
from .models import ImplicitSpan
from collections import defaultdict

sys.path.append(os.environ['SNORKELHOME'] + '/treedlib/treedlib')

def compile_entity_feature_generator():
  """
  Given optional arguments, returns a generator function which accepts an xml root
  and a list of indexes for a mention, and will generate relation features for this entity
  """

  BASIC_ATTRIBS_REL = ['lemma', 'dep_label']

  m = Mention(0)

  # Basic relation feature templates
  temps = [
    [Indicator(m, a) for a in BASIC_ATTRIBS_REL],
    Indicator(m, 'dep_label,lemma'),
    # The *first element on the* path to the root: ngram lemmas along it
    Ngrams(Parents(m, 3), 'lemma', (1,3)),
    Ngrams(Children(m), 'lemma', (1,3)),
    # The siblings of the mention
    [LeftNgrams(LeftSiblings(m), a) for a in BASIC_ATTRIBS_REL],
    [RightNgrams(RightSiblings(m), a) for a in BASIC_ATTRIBS_REL]
  ]

  # return generator function
  return Compile(temps).apply_mention

def get_ddlib_feats(context, idxs):
  """
  Minimalist port of generic mention features from ddlib
  """
  for seq_feat in _get_seq_features(context, idxs):
    yield seq_feat

  for window_feat in _get_window_features(context, idxs):
    yield window_feat

  if context['words'][idxs[0]][0].isupper():
      yield "STARTS_WITH_CAPITAL"

  yield "LENGTH_{}".format(len(idxs))

def _get_seq_features(context, idxs):
  yield "WORD_SEQ_[" + " ".join(context['words'][i] for i in idxs) + "]"
  yield "LEMMA_SEQ_[" + " ".join(context['lemmas'][i] for i in idxs) + "]"
  yield "POS_SEQ_[" + " ".join(context['pos_tags'][i] for i in idxs) + "]"
  yield "DEP_SEQ_[" + " ".join(context['dep_labels'][i] for i in idxs) + "]"

def _get_window_features(context, idxs, window=3, combinations=True, isolated=True):
    left_lemmas = []
    left_pos_tags = []
    right_lemmas = []
    right_pos_tags = []
    try:
        for i in range(1, window + 1):
            lemma = context['lemmas'][idxs[0] - i]
            try:
                float(lemma)
                lemma = "_NUMBER"
            except ValueError:
                pass
            left_lemmas.append(lemma)
            left_pos_tags.append(context['pos_tags'][idxs[0] - i])
    except IndexError:
        pass
    left_lemmas.reverse()
    left_pos_tags.reverse()
    try:
        for i in range(1, window + 1):
            lemma = context['lemmas'][idxs[-1] + i]
            try:
                float(lemma)
                lemma = "_NUMBER"
            except ValueError:
                pass
            right_lemmas.append(lemma)
            right_pos_tags.append(context['pos_tags'][idxs[-1] + i])
    except IndexError:
        pass
    if isolated:
        for i in range(len(left_lemmas)):
            yield "W_LEFT_" + str(i+1) + "_[" + " ".join(left_lemmas[-i-1:]) + \
                "]"
            yield "W_LEFT_POS_" + str(i+1) + "_[" + " ".join(left_pos_tags[-i-1:]) +\
                "]"
        for i in range(len(right_lemmas)):
            yield "W_RIGHT_" + str(i+1) + "_[" + " ".join(right_lemmas[:i+1]) +\
                "]"
            yield "W_RIGHT_POS_" + str(i+1) + "_[" + \
                " ".join(right_pos_tags[:i+1]) + "]"
    if combinations:
        for i in range(len(left_lemmas)):
            curr_left_lemmas = " ".join(left_lemmas[-i-1:])
            try:
                curr_left_pos_tags = " ".join(left_pos_tags[-i-1:])
            except TypeError:
                new_pos_tags = []
                for pos in left_pos_tags[-i-1:]:
                    to_add = pos
                    if not to_add:
                        to_add = "None"
                    new_pos_tags.append(to_add)
                curr_left_pos_tags = " ".join(new_pos_tags)
            for j in range(len(right_lemmas)):
                curr_right_lemmas = " ".join(right_lemmas[:j+1])
                try:
                    curr_right_pos_tags = " ".join(right_pos_tags[:j+1])
                except TypeError:
                    new_pos_tags = []
                    for pos in right_pos_tags[:j+1]:
                        to_add = pos
                        if not to_add:
                            to_add = "None"
                        new_pos_tags.append(to_add)
                    curr_right_pos_tags = " ".join(new_pos_tags)
                yield "W_LEMMA_L_" + str(i+1) + "_R_" + str(j+1) + "_[" + \
                    curr_left_lemmas + "]_[" + curr_right_lemmas + "]"
                yield "W_POS_L_" + str(i+1) + "_R_" + str(j+1) + "_[" + \
                    curr_left_pos_tags + "]_[" + curr_right_pos_tags + "]"

def tablelib_unary_features(span):
    """
    Table-/structure-related features for a single span 
    """
    yield "SPAN_TYPE_[%s]" % ('IMPLICIT' if isinstance(span, ImplicitSpan) else 'EXPLICIT') 
    phrase = span.parent
    if phrase.html_tag:
        yield u"HTML_TAG_" + phrase.html_tag
    # for attr in phrase.html_attrs:
    #     yield u"HTML_ATTR_[" + attr + "]"
    if phrase.html_anc_tags:
        for tag in phrase.html_anc_tags:
            yield u"HTML_ANC_TAG_[" + tag + "]"
    # for attr in phrase.html_anc_attrs:
        # yield u"HTML_ANC_ATTR_[" + attr + "]"
    for attrib in ['words']: #,'lemmas', 'pos_tags', 'ner_tags']:
        for ngram in span.get_attrib_tokens(attrib):
            yield "CONTAINS_%s_[%s]" % (attrib.upper(), ngram)
        for ngram in get_left_ngrams(span, window=7, n_max=2, attrib=attrib):
            yield "LEFT_%s_[%s]" % (attrib.upper(), ngram)
        for ngram in get_right_ngrams(span, window=7, n_max=2, attrib=attrib):
            yield "RIGHT_%s_[%s]" % (attrib.upper(), ngram)
        if phrase.row_start is None or phrase.col_start is None:
            for ngram in get_neighbor_phrase_ngrams(span, d=1, n_max=2, attrib=attrib):
                yield "NEIGHBOR_PHRASE_%s_[%s]" % (attrib.upper(), ngram)
        else:
            for ngram in get_cell_ngrams(span, n_max=2, attrib=attrib):
                yield "CELL_%s_[%s]" % (attrib.upper(), ngram)
            for row_num in range(phrase.row_start, phrase.row_end + 1):
                yield "ROW_NUM_[%s]" % row_num
            for col_num in range(phrase.col_start, phrase.col_end + 1):
                yield "COL_NUM_[%s]" % col_num
            # NOTE: These two features should be accounted for by HTML_ATTR_ 
            yield "ROW_SPAN_[%d]" % num_rows(phrase)
            yield "COL_SPAN_[%d]" % num_cols(phrase)
            for axis in ['row', 'col']:
                for ngram in get_head_ngrams(span, axis, n_max=2, attrib=attrib):
                    yield "%s_HEAD_%s_[%s]" % (axis.upper(), attrib.upper(), ngram)
            for ngram in get_row_ngrams(span, n_max=2, attrib=attrib):
                yield "ROW_%s_[%s]" % (attrib.upper(), ngram)
            for ngram in get_col_ngrams(span, n_max=2, attrib=attrib):
                yield "COL_%s_[%s]" % (attrib.upper(), ngram)
            for ngram in get_row_ngrams(span, n_max=2, attrib=attrib, direct=False, infer=True):
                yield "ROW_INFERRED_%s_[%s]" % (attrib.upper(), ngram)         
            for ngram in get_col_ngrams(span, n_max=2, attrib=attrib, direct=False, infer=True):
                yield "COL_INFERRED_%s_[%s]" % (attrib.upper(), ngram)         
            # for (ngram, direction) in get_neighbor_cell_ngrams(span, dist=2, directions=True, n_max=3, attrib=attrib):
            #     yield "NEIGHBOR_%s_%s_[%s]" % (direction, attrib.upper(), ngram)
            #     if attrib=="lemmas":
            #         try:
            #             if float(ngram).is_integer():
            #                 yield "NEIGHBOR_%s_INT" % side
            #             else:
            #                 yield "NEIGHBOR_%s_FLOAT" % side
            #         except:
            #             pass

def tablelib_binary_features(span1, span2):
    """
    Table-/structure-related features for a pair of spans 
    """
    for feat in tablelib_unary_features(span1):
        yield "e1_" + feat
    for feat in tablelib_unary_features(span2):
        yield "e2_" + feat
    if span1.parent.table is not None and span2.parent.table is not None:
        if span1.parent.table == span2.parent.table:
            yield u"SAME_TABLE"
            if span1.parent.cell is not None and span2.parent.cell is not None:
                row_diff = min_row_diff(span1.parent, span2.parent, absolute=False) 
                col_diff = min_col_diff(span1.parent, span2.parent, absolute=False)  
                yield u"SAME_TABLE_ROW_DIFF_[%s]" % row_diff
                yield u"SAME_TABLE_COL_DIFF_[%s]" % col_diff
                yield u"SAME_TABLE_MANHATTAN_DIST_[%s]" % str(abs(row_diff) + abs(col_diff))
                if span1.parent.cell == span2.parent.cell:
                    yield u"SAME_CELL"
                    yield u"WORD_DIFF_[%s]" % (span1.get_word_start() - span2.get_word_start())
                    yield u"CHAR_DIFF_[%s]" % (span1.char_start - span2.char_start)
                    if span1.parent == span2.parent:
                        yield u"SAME_PHRASE"
        else:
            if span1.parent.cell is not None and span2.parent.cell is not None:
                row_diff = min_row_diff(span1.parent, span2.parent, absolute=False) 
                col_diff = min_col_diff(span1.parent, span2.parent, absolute=False)
                yield u"DIFF_TABLE_ROW_DIFF_[%s]" % row_diff
                yield u"DIFF_TABLE_COL_DIFF_[%s]" % col_diff
                yield u"DIFF_TABLE_MANHATTAN_DIST_[%s]" % str(abs(row_diff) + abs(col_diff))

##################################################################################
# Visual features
##################################################################################
from lf_helpers import _bbox_from_span    

def vizlib_unary_features(span):
    """
    Visual-related features for a single span
    """
    for f in get_visual_aligned_lemmas(span):
        yield 'ALIGNED_' + f
    
    for page in set(span.get_attrib_tokens('page')): 
        yield "PAGE_[%d]" % page

def vizlib_binary_features(span1, span2):
    """
    Visual-related features for a pair of spans
    """
    for feat in vizlib_unary_features(span1):
        yield "e1_" + feat
    for feat in vizlib_unary_features(span2):
        yield "e2_" + feat

    if same_page((span1, span2)):
        yield "SAME_PAGE"

        if is_horz_aligned((span1, span2)):
            yield "HORZ_ALIGNED"
        
        if is_vert_aligned((span1, span2)):
            yield "VERT_ALIGNED"

        if is_vert_aligned_left((span1, span2)):
            yield "VERT_ALIGNED_LEFT"

        if is_vert_aligned_right((span1, span2)):
            yield "VERT_ALIGNED_RIGHT"

        if is_vert_aligned_center((span1, span2)):
            yield "VERT_ALIGNED_CENTER"