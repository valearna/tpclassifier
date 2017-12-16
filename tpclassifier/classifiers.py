"""Train and apply document classifiers for Textpresso literature"""

import os
import random
from sklearn import metrics, feature_selection
from namedlist import namedlist
from tpclassifier.fileutils import *
from sklearn.feature_extraction.text import TfidfVectorizer, HashingVectorizer, TfidfTransformer, CountVectorizer
from typing import Tuple
from nltk import word_tokenize
from nltk.stem import WordNetLemmatizer

__author__ = "Valerio Arnaboldi"

__version__ = "1.0.1"


DatasetStruct_ = namedlist("DatasetStruct", "data, filenames, target, tr_features")
TestResults_ = namedlist("TestResults", "precision, recall, accuracy, roc")


class TokenizerType(Enum):
    BOW = 1
    TFIDF = 2
    HASH = 3


class DatasetStruct(DatasetStruct_):
    """structure that defines fields of a dataset

    This data structure is used to store the properties of training sets and test sets within the models, so that the
    textual content and the file names of the documents used to create the classifiers are included with them and they
    can be easily retrieved.
    """
    pass


class TestResults(TestResults_):
    """List that contains the different values obtained while testing a classifier"""
    pass


class LemmaTokenizer(object):
    def __init__(self):
        self.wnl = WordNetLemmatizer()

    def __call__(self, doc):
        return [self.wnl.lemmatize(t) for t in word_tokenize(doc)]


class TextpressoDocumentClassifier:

    def __init__(self):
        self.dataset = DatasetStruct(data=[], filenames=[], target=[], tr_features=None)
        self.training_set = DatasetStruct(data=[], filenames=[], target=[], tr_features=None)
        self.test_set = DatasetStruct(data=[], filenames=[], target=[], tr_features=None)
        self.classifier = None
        self.vectorizer = None
        self.feature_selector = None
        self.top_n_feat = 0

    def add_classified_docs_to_dataset(self, dir_path: str = None, recursive: bool = True,
                                       file_type: str = "pdf", category: int = 1):
        """load the text from the cas files in the specified directory and add them to the dataset,
        assigning them to the specified category (class)

        Note that only files with .tpcas.gz extension will be loaded

        :param dir_path: the path to the directory containing the text files to be added to the dataset
        :type dir_path: str
        :param recursive: scan directory recursively
        :type recursive: bool
        :param file_type: the type of cas files from which to extract the fulltext
        :type file_type: str
        :param category: the category value to be associated with the documents
        :type category: int
        """
        for file in os.listdir(dir_path):
            if not os.path.isdir(os.path.join(dir_path, file)):
                if file_type == "pdf":
                    data = extract_text_from_pdf(file_path=os.path.join(dir_path, file))
                    if data is not None:
                        self.dataset.data.append(data)
                elif file_type == "cas_pdf" or file_type == "cas_xml":
                    if file_type == "cas_pdf":
                        cas_type = CasType.PDF
                    else:
                        cas_type = CasType.XML
                    self.dataset.data.append(extract_text_from_cas_content(
                        cas_content=read_compressed_cas_content(file_path=os.path.join(dir_path, file)),
                        cas_type=cas_type))
                self.dataset.filenames.append(file)
                self.dataset.target.append(category)
            elif recursive:
                self.add_classified_docs_to_dataset(dir_path=os.path.join(dir_path, file), recursive=True,
                                                    file_type=file_type, category=category)

    def generate_training_and_test_sets(self, percentage_training: float = 0.8):
        """split the dataset into training and test sets

        :param percentage_training: the percentage of observations to be placed in the training set
        :type percentage_training: float
        """
        if len(self.dataset.data) > 0:
            idx_rand_order = list(range(len(self.dataset.data)))
            random.shuffle(idx_rand_order)
            training_set_idx = idx_rand_order[:int(len(idx_rand_order) * percentage_training)]
            test_set_idx = idx_rand_order[int(len(idx_rand_order) * percentage_training):]
            self.training_set.data = [self.dataset.data[i] for i in training_set_idx]
            self.training_set.filenames = [self.dataset.filenames[i] for i in training_set_idx]
            self.training_set.target = [self.dataset.target[i] for i in training_set_idx]
            self.test_set.data = [self.dataset.data[i] for i in test_set_idx]
            self.test_set.filenames = [self.dataset.filenames[i] for i in test_set_idx]
            self.test_set.target = [self.dataset.target[i] for i in test_set_idx]

    def extract_features(self, tokenizer_type: TokenizerType = TokenizerType.BOW, ngram_range: Tuple[int, int] = (1, 1),
                         lemmatization: bool = False, top_n_feat: int = None, stop_words = "english",
                         max_df: float = 1.0, max_features: int = None):
        """perform feature extraction with tfidf normalization on training and test sets and store the transformed
        features

        :param tokenizer_type: the type of tokenizer to use for feature extraction
        :type tokenizer_type: TokenizerType
        :param ngram_range: The lower and upper boundary of the range of n-values for different n-grams to be extracted.
            All values of n such that min_n <= n <= max_n will be used.
        :type ngram_range: Tuple[int, int]
        :param lemmatization: whether to apply lemmatization to the text
        :type lemmatization: bool
        :param top_n_feat: select the best n features through feature selection
        :type top_n_feat: int
        :param stop_words: stop words to use
        :param max_df: max_df to use
        :type max_df: float
        :param max_features: consider only the best n features sorted by tfidf
        :type max_features: int
        """
        if tokenizer_type == TokenizerType.BOW:
            if lemmatization:
                self.vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=ngram_range,
                                                  tokenizer=LemmaTokenizer(), max_df=max_df, max_features=max_features)
            else:
                self.vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=ngram_range, max_df=max_df,
                                                  max_features=max_features)
            self.training_set.tr_features = self.vectorizer.fit_transform(self.training_set.data)
            if len(self.test_set.data) > 0:
                self.test_set.tr_features = self.vectorizer.transform(self.test_set.data)
        elif tokenizer_type == TokenizerType.HASH:
            if lemmatization:
                self.vectorizer = HashingVectorizer(stop_words=stop_words, ngram_range=ngram_range,
                                                    tokenizer=LemmaTokenizer())
            else:
                self.vectorizer = HashingVectorizer(stop_words=stop_words, ngram_range=ngram_range)
            tfidf_transformer = TfidfTransformer()
            train_counts = self.vectorizer.transform(self.training_set.data)
            self.training_set.tr_features = tfidf_transformer.fit_transform(train_counts)
            if len(self.test_set.data) > 0:
                test_counts = self.vectorizer.transform(self.test_set.data)
                self.test_set.tr_features = tfidf_transformer.transform(test_counts)
        elif tokenizer_type == TokenizerType.TFIDF:
            if lemmatization:
                self.vectorizer = TfidfVectorizer(stop_words=stop_words, ngram_range=ngram_range,
                                                  tokenizer=LemmaTokenizer(), max_df=max_df, max_features=max_features)
            else:
                self.vectorizer = TfidfVectorizer(stop_words=stop_words, ngram_range=ngram_range, max_df=max_df,
                                                  max_features=max_features)
            self.training_set.tr_features = self.vectorizer.fit_transform(self.training_set.data)
            if len(self.test_set.data) > 0:
                self.test_set.tr_features = self.vectorizer.transform(self.test_set.data)
        if top_n_feat is not None:
            fs = feature_selection.chi2(self.training_set.tr_features, self.training_set.target)
            best_features_idx = sorted(range(len(fs[0])), key=lambda k: fs[0][k], reverse=True)
            self.training_set.tr_features = self.training_set.tr_features[:, best_features_idx[:top_n_feat]]
            if len(self.test_set.data) > 0:
                self.test_set.tr_features = self.test_set.tr_features[:, best_features_idx[:top_n_feat]]
            self.feature_selector = fs
            self.top_n_feat = top_n_feat

    def train_classifier(self, model, dense: bool = False):
        """train a classifier using the sample documents in the training set and save the trained model

        :param model: the model to train
        :param dense: whether to transform the sparse matrix of features to a dense structure (required by some models)
        :type dense: bool
        """
        self.classifier = model
        if dense:
            self.classifier.fit(self.training_set.tr_features.todense(), self.training_set.target)
        else:
            self.classifier.fit(self.training_set.tr_features, self.training_set.target)

    def test_classifier(self, test_on_training: bool = False, dense: bool = False):
        """test the classifier on the test set and return the results

        :param test_on_training: whether to test the classifier on the training set instead of the test set
        :type test_on_training: bool
        :param dense: whether to transform the sparse matrix of features to a dense structure (required by some models)
        :type dense: bool
        :return: the test results of the classifier
        :rtype: TestResults"""
        if test_on_training:
            test_set = self.training_set
        else:
            test_set = self.test_set
        if dense:
            pred = self.classifier.predict(test_set.tr_features.todense())
        else:
            pred = self.classifier.predict(test_set.tr_features)
        precision = metrics.precision_score(test_set.target, pred)
        recall = metrics.recall_score(test_set.target, pred)
        accuracy = metrics.accuracy_score(test_set.target, pred)
        roc = metrics.roc_curve(test_set.target, pred)
        return TestResults(precision, recall, accuracy, roc)

    def predict_file(self, file_path: str, file_type: str = "pdf", dense: bool = False):
        """predict the class of a single file

        :param file_path: the path to the file
        :type file_path: str
        :param file_type: the type of file
        :type file_type: str
        :param dense: whether to transform the sparse matrix of features to a dense structure (required by some models)
        :type dense: bool
        :return: the class predicted by the classifier
        :rtype: int
        """
        if file_type == "pdf":
            fulltext = extract_text_from_pdf(file_path)
        else:
            if file_type == "cas_pdf":
                cas_type = CasType.PDF
            else:
                cas_type = CasType.XML
            fulltext = extract_text_from_cas_content(read_compressed_cas_content(file_path=file_path),
                                                     cas_type=cas_type)
        tr_features = self.vectorizer.transform([fulltext])
        if self.feature_selector is not None:
            best_features_idx = sorted(range(len(self.feature_selector[0])), key=lambda k: self.feature_selector[0][k],
                                       reverse=True)
            tr_features = tr_features[:, best_features_idx[:self.top_n_feat]]
        if dense:
            return self.classifier.predict(self.vectorizer.transform(tr_features))
        else:
            return self.classifier.predict(self.vectorizer.transform(tr_features))

    def predict_files(self, dir_path: str, file_type: str = "pdf", dense: bool = False):
        """predict the class of a set of files in a directory

        :param dir_path: the path to the directory containg the files to be classified
        :type dir_path: str
        :param file_type: the type of files
        :type file_type: str
        :param dense: whether to transform the sparse matrix of features to a dense structure (required by some models)
        :type dense: bool
        :return: the file names of the classified documents along with the classes predicted by the classifier
        :rtype: Tuple[List[str], List[int]]
        """
        data = []
        filenames = []
        for file in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file)
            if file_type == "pdf":
                text = extract_text_from_pdf(file_path)
                if text is None:
                    continue
                data.append(extract_text_from_pdf(file_path))
            else:
                if file_type == "cas_pdf":
                    cas_type = CasType.PDF
                else:
                    cas_type = CasType.XML
                data.append(extract_text_from_cas_content(read_compressed_cas_content(file_path=file_path),
                            cas_type=cas_type))
            filenames.append(file)
        tr_features = self.vectorizer.transform(data)
        if self.feature_selector is not None:
            best_features_idx = sorted(range(len(self.feature_selector[0])), key=lambda k: self.feature_selector[0][k],
                                       reverse=True)
            tr_features = tr_features[:, best_features_idx[:self.top_n_feat]]
        if dense:
            return filenames, self.classifier.predict(tr_features.todense())
        else:
            return filenames, self.classifier.predict(tr_features)
