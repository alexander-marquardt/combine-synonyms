#!/usr/bin/env python3

import os
import sys
import datetime
import getpass
import socket
from collections import defaultdict

"""
This Python script combines multiple synonym files from a specified directory into a single output file.
It ensures that each synonym expansion (one-way synonyms) only has one `=>` operator per line, handling self-mapping properly.
It also ensures that one-way synonyms expand to include themselves, with valid Elasticsearch syntax.
"""


def parse_synonym_line(line):
    """
    Parse a synonym line into a set of terms.
    This ensures we can compare synonym lines regardless of term order.
    """
    if "=>" in line:
        # Handle one-way expansion: left-hand side (term) => right-hand side (synonyms)
        left, right = line.split("=>")
        left_term = left.strip()
        right_terms = [term.strip() for term in right.split(",")]
        return left_term, set(right_terms)
    else:
        # Handle two-way expansion: comma-separated list of synonyms
        return None, set(term.strip() for term in line.split(","))


def merge_synonym_sets(existing_synonyms, new_synonym_set, synonym_map, left_term=None):
    """
    Merges any existing synonym sets that have overlap with the new synonym set.
    Also populates synonym_map for potential one-way detection.
    """
    to_merge = []

    # Find all synonym sets that overlap with the new set
    for synonym_set in existing_synonyms:
        if not synonym_set.isdisjoint(new_synonym_set):
            to_merge.append(synonym_set)

    # Merge all overlapping sets into a single set
    for synonym_set in to_merge:
        existing_synonyms.remove(synonym_set)
        new_synonym_set.update(synonym_set)

    # Add the newly merged set to the collection
    existing_synonyms.append(new_synonym_set)

    # Track synonym mapping for one-way detection, especially for left-hand side of "=>"
    if left_term:
        synonym_map[left_term].update(new_synonym_set)
    else:
        for term in new_synonym_set:
            synonym_map[term].update(new_synonym_set)


def combine_synonym_files_in_directory(directory):
    """
    Combine all synonym files in the specified directory into one, removing duplicates and appending new synonyms.
    :param directory: Directory containing synonym files.
    :return: A list of combined synonym lines, and a list of file paths that were combined.
    """
    combined_synonyms = []
    file_paths = []
    synonym_map = defaultdict(set)  # Keeps track of all synonyms for potential one-way detection

    # Scan directory for all .txt files
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory, filename)
            file_paths.append(file_path)
            print(f"Processing file: {file_path}")

            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        # Ignore empty lines and comments
                        continue

                    left_term, new_synonym_set = parse_synonym_line(line)
                    merge_synonym_sets(combined_synonyms, new_synonym_set, synonym_map, left_term)

    # Convert sets back into sorted comma-separated lines
    combined_synonym_lines = [", ".join(sorted(synonym_set)) for synonym_set in combined_synonyms]
    return combined_synonym_lines, file_paths, synonym_map


def detect_one_way_synonyms(synonym_map):
    """
    Detect potential one-way (unidirectional) synonyms where a term has ambiguous meanings.
    Returns a list of one-way rules.
    Ensures that each term is expanded to itself and other synonyms with valid syntax.
    """
    one_way_synonyms = []

    for term, synonyms in synonym_map.items():
        expanded_synonyms = sorted(synonyms - {term})  # Remove the term itself from the list
        if expanded_synonyms:
            # Add the term back and expand it to all synonyms
            one_way_synonyms.append(f"{term} => {term}, {', '.join(expanded_synonyms)}")
        else:
            # If no synonyms are found, keep the term mapping to itself (self-mapping)
            one_way_synonyms.append(f"{term} => {term}")

    return one_way_synonyms


def write_combined_synonyms(output_file, combined_synonyms, file_paths, one_way_synonyms):
    """
    Write the combined synonym list to a new file with an introductory header, metadata, and one-way synonym rules.
    Each one-way synonym is written on a separate line to ensure correct Elasticsearch handling.

    :param output_file: Output file path.
    :param combined_synonyms: List of combined synonym lines.
    :param file_paths: List of paths of the files that were combined.
    :param one_way_synonyms: List of one-way synonym rules.
    """
    # Get metadata: timestamp, user, and hostname
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user = getpass.getuser()
    hostname = socket.gethostname()

    with open(output_file, 'w') as f:
        # Write the introductory header
        f.write("# This file contains combined synonym sets generated by merging multiple synonym files.\n")
        f.write(
            "# Synonym sets with overlapping terms are merged into a single set, and duplicate entries are removed.\n")
        f.write(
            "# Each line contains synonyms, separated by commas, which can be used in Elasticsearch or other search systems.\n")
        f.write("# The lines are automatically deduplicated and sorted for clarity and performance.\n")
        f.write("# Example:\n")
        f.write("# power plant => power plant, power station, generating station, generation facility\n\n")

        # Add warning about human review and possible errors
        f.write("# IMPORTANT: This combined synonym file should be reviewed by a human to ensure accuracy.\n")
        f.write("# One-way synonyms are written on separate lines to ensure correct handling in Elasticsearch.\n\n")

        # Write metadata
        f.write(f"# Files combined:\n")
        for file_path in file_paths:
            f.write(f"# - {file_path}\n")
        f.write(f"\n# Timestamp: {timestamp}\n")
        f.write(f"# User: {user}\n")
        f.write(f"# Hostname: {hostname}\n\n")

        # Write one-way synonym rules
        if one_way_synonyms:
            f.write("# One-way synonym rules detected:\n")
            for expansion in one_way_synonyms:
                f.write(f"{expansion}\n")
            f.write("\n")

        # Write the combined synonym lines
        f.write("# Standard synonyms:\n")
        for line in sorted(combined_synonyms):
            f.write(line + '\n')


def main():
    """
    Main function to combine all synonym files in a specified directory and save the output with a header and metadata.

    :param directory: Directory containing synonym files passed as a command-line argument.
    :param output_file: The output file path where the combined synonyms will be saved.
    """
    if len(sys.argv) != 3:
        print("Usage: python combine_synonyms.py <directory> <output_file>")
        sys.exit(1)

    directory = sys.argv[1]  # Get directory from command line argument
    output_file = sys.argv[2]  # Get output file name from command line argument

    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        sys.exit(1)

    combined_synonyms, file_paths, synonym_map = combine_synonym_files_in_directory(directory)

    # Detect potential one-way synonyms
    one_way_synonyms = detect_one_way_synonyms(synonym_map)

    # Write the combined synonym file
    write_combined_synonyms(output_file, combined_synonyms, file_paths, one_way_synonyms)
    print(f"Combined synonyms written to {output_file}")


if __name__ == "__main__":
    main()
