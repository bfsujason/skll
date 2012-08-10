#!/usr/bin/env python
"""
Join MegaM files

@author: Dan Blanchard, dblanchard@ets.org
@date: July 2012
"""

from __future__ import print_function, unicode_literals

import argparse
import os
import re
import sys
from collections import defaultdict
from itertools import izip, islice

from bs4 import UnicodeDammit


def parse_num_list(num_string):
    '''
        Convert a string representing a range of numbers to a list of integers.
    '''
    range_list = []
    if (num_string != '') and (not re.match(r'^(\d+(-\d+)?,)*\d+(-\d+)?$', num_string)):
        raise argparse.ArgumentTypeError("'" + num_string + "' is not a range of numbers. Expected forms are '8-15', '4,8,15,16,23,42', or '8-15,42'.")
    for rng in num_string.split(','):
        if rng.count('-'):
            split_range = [int(x) for x in rng.split('-')]
            split_range[1] += 1
            range_list.extend(range(*split_range))
        else:
            range_list.append(int(rng))
    return range_list


if __name__ == '__main__':
    # Get command line arguments
    parser = argparse.ArgumentParser(description="Combine MegaM files that contain features for the same files.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('megam_file', help='MegaM input file(s). Each feature line must be preceded by a comment with the filename/ID ' +
                                           'that the features should be joined on.', type=argparse.FileType('r'), nargs='+')
    parser.add_argument('-b', '--binary', help='Converts all of the features in the specified range of files to presence/absence binary features. Files are numbered ' +
                                               'starting from 1, and if 0 is specified with this flag, all files are converted.', type=parse_num_list)
    parser.add_argument('--doubleup', help='Keep both the binary and numeric versions of any feature you convert to binary.', action='store_true')
    args = parser.parse_args()

    # Map from filenames to feature strings
    feature_dict = defaultdict(unicode)
    class_dict = dict()

    # Set that will contain all of the features seen in previous files (for duplicate detection)
    prev_feature_set = set()

    # Iterate through MegaM files
    for file_num, infile in enumerate(args.megam_file, start=1):
        # Initialize duplicate feature book-keeping variables
        curr_feature_set = set()
        warned_about = dict()

        # Handle current MegaM file
        print("Loading {}...".format(infile.name), file=sys.stderr)
        sys.stderr.flush()
        for line in infile:
            stripped_line = UnicodeDammit(line.strip(), ['utf-8', 'windows-1252']).unicode_markup
            # Read current filename from comment
            if stripped_line.startswith('#'):
                curr_filename = stripped_line.lstrip('# ')
            # Ignore TEST and DEV lines and store features
            elif stripped_line not in ['TEST', 'DEV']:
                split_line = stripped_line.split('\t', 1)
                # Only proceed if there are features on the line
                if len(split_line) == 2:
                    class_dict[curr_filename] = split_line[0]
                    feature_pairs = split_line[1].split(' ')
                    feature_names = feature_pairs[0::2]
                    if len(feature_names) != len(set(feature_names)):
                        print("Error: Duplicate features occur on the line of features for {}.".format(curr_filename), file=sys.stderr)
                        sys.exit(1)
                    feature_values = islice(feature_pairs, 1, None, 2)
                    for feat_name, feat_val in izip(feature_names, feature_values):
                        # Handle duplicate features
                        if feat_name in prev_feature_set:
                            new_feat_name = feat_name
                            # Add suffix multiple times if necessary
                            while new_feat_name in prev_feature_set:
                                new_feat_name += "_" + os.path.splitext(os.path.basename(infile.name))[0].replace(' ', '_')
                            if feat_name not in warned_about:
                                print("Warning: Feature named {} already found in previous files. Renaming to {} to prevent duplicates.".format(feat_name, new_feat_name),
                                      file=sys.stderr)
                                warned_about[feat_name] = True
                            feat_name = new_feat_name
                        # Ignore zero-valued features
                        try:
                            if feat_val != 'N/A' and float(feat_val) != 0:
                                # Convert feature to binary if necessary
                                if (args.binary and ((args.binary == [0]) or (file_num in args.binary))):
                                    if args.doubleup:
                                        feature_dict[curr_filename] += '{} {} '.format(feat_name, feat_val)
                                        curr_feature_set.add(feat_name)
                                        feat_name = feat_name + "_binary"
                                    feat_val = 1

                                # Add feature pair to current string of features
                                feature_dict[curr_filename] += '{} {} '.format(feat_name, feat_val)
                                curr_feature_set.add(feat_name)
                        except ValueError:
                            print("Error: Invalid feature value in feature pair '{} {}' for file {}".format(feat_name, feat_val, curr_filename), file=sys.stderr)
                            sys.exit(1)

                # Otherwise warn about lack of features (although that really just means all of them have zero values)
                else:
                    print("Warning: No features found for {} in {}".format(curr_filename, infile.name), file=sys.stderr)

        # Add current file's features to set of seen features
        prev_feature_set.update(curr_feature_set)

    # Print new MegaM file
    for curr_filename in feature_dict.viewkeys():
        print("# {}".format(curr_filename).encode('utf-8'))
        print("{}\t{}".format(class_dict[curr_filename], feature_dict[curr_filename].strip()).encode('utf-8'))
