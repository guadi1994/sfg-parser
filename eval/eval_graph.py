from pathlib import Path
import typer
import json
from tabulate import tabulate


def count_nodes(graphs):
    """
    Count number of nodes.
    """

    counter = 0
    for graph in graphs:
        for node in graph:
            if not is_punct(node):
                counter += 1

    return counter


def count_nodes_per_label(graphs):
    """
    Count number of nodes per label.
    """

    counter = {}
    for graph in graphs:
        for node in graph:
            label = node["tag"]
            if label not in counter:
                counter[label] = 1
            else:
                counter[label] += 1

    return counter


def count_ellipsed_edges(graphs):
    """
    Count number of nodes with ellipsed edges.
    """

    counter = 0
    for graph in graphs:
        for node in graph:
            if not is_punct(node) and len(node["ellipsed_parents"]) > 0:
                counter += 1

    return counter


def count_ellipsed_edges_per_label(graphs):
    """
    Count number of nodes with ellipsed edges per label.
    """

    counter = {}
    for graph in graphs:
        for node in graph:
            label = node["tag"]
            if label not in counter and not is_punct(node) and len(node["ellipsed_parents"]) > 0:
                counter[label] = 1
            elif label in counter and not is_punct(node) and len(node["ellipsed_parents"]) > 0:
                counter[label] += 1

    return counter


def get_parents(graph, node):
    """
    Get unellipsed and ellipsed parents for a node.
    """

    parent = graph[node]["parent"]
    ellipsed_parents = graph[node]["ellipsed_parents"]

    return parent, ellipsed_parents


def get_position(graph, parent, node):
    """
    Get position of a node among siblings.
    """

    children = [child for child in graph[parent]["children"] if child in graph]
    for position, child in enumerate(children):
        if child == node:
            return position


def is_punct(node):
    """
    Check whether a node is punctuation.
    """

    if node["tag"] in [",", ":", "``", '"', "-LRB-", "-RRB-"]:
        return True
    else:
        return False


def edge_is_correct(gold_graph, predicted_graph, node, exclude_ellipsis, ellipsis_only):
    """
    Check that a node has the correct parents.
    When ellipsed, check that the node is inserted in the right position.
    """

    # IDK IF THIS IS THE BEST WAY TO HANDLE THIS, IT AFFECTS THE SCORES BY 2 POINTS IF I SET IT TO TRUE
    # THIS HAPPENS WHEN THERE IS NOT A PREDICTED EDGE WITH THE SAME ID, IT HAPPENS WHEN GETTING RID OF PUNCTUATION ESPECIALLY
    if node not in predicted_graph:
        return False

    predicted_parent, predicted_parents_ellipsed = get_parents(predicted_graph, node)
    gold_parent, gold_parents_ellipsed = get_parents(gold_graph, node)

    # check only non-ellipsed edges
    if exclude_ellipsis:
        if predicted_parent != gold_parent:
            return False  

    # check only ellipsed edges
    elif ellipsis_only:
        if set(predicted_parents_ellipsed) != set(gold_parents_ellipsed) or len(gold_parents_ellipsed) == 0:
            return False
        # check if the node is inserted in a wrong position
        else:
            for parent in predicted_parents_ellipsed:
                predicted_position = get_position(predicted_graph, parent, node)
                gold_position = get_position(gold_graph, parent, node)     
                if predicted_position != gold_position:
                    return False  

    # check ellipsed and non-ellipsed edges
    else:
        if set([predicted_parent,] + predicted_parents_ellipsed) != set([gold_parent,] + gold_parents_ellipsed):
            return False
        # when ellipsed, check if the node is inserted in a wrong position
        else:
            for parent in predicted_parents_ellipsed:
                predicted_position = get_position(predicted_graph, parent, node)
                gold_position = get_position(gold_graph, parent, node)     
                if predicted_position != gold_position:
                    return False

    return True


def label_is_correct(gold_graph, predicted_graph, node, exclude_ellipsis, ellipsis_only):
    """
    Check that a node has the correct label.
    """

    predicted_label = predicted_graph[node]["tag"]
    gold_label = gold_graph[node]["tag"]

    if predicted_label == gold_label:
        return True
    else:
        return False


def get_graphs(json_file):
    """
    Extract graphs from a json file.
    """

    graphs = []

    with json_file.open(mode="r") as f:
        docs = json.load(f)

    for doc in docs["docs"]:
        for sent in doc["sents"]:
            graph = sent["graph"]
            graphs.append(graph)

    return graphs


def score(gold_graphs, predicted_graphs, exclude_ellipsis=False, ellipsis_only=False):
    """
    Evaluate graphs.
    """

    if ellipsis_only:
        gold_nodes = count_ellipsed_edges(gold_graphs)
        predicted_nodes = count_ellipsed_edges(predicted_graphs)   
        gold_per_label = count_ellipsed_edges_per_label(gold_graphs)
        predicted_per_label = count_ellipsed_edges_per_label(predicted_graphs)        
    else:     
        gold_nodes = count_nodes(gold_graphs)
        predicted_nodes = count_nodes(predicted_graphs)
        gold_per_label = count_nodes_per_label(gold_graphs)
        predicted_per_label = count_nodes_per_label(predicted_graphs)      
    correct_unlabeled = 0
    correct_labeled = 0
    correct_per_label = {}

    for gold_graph, predicted_graph in zip(gold_graphs, predicted_graphs):
        gold_graph = {node["id"]:node for node in gold_graph if not is_punct(node)}
        predicted_graph = {node["id"]:node for node in predicted_graph if not is_punct(node)}
        # count number of correct nodes
        for node in gold_graph:
            label = gold_graph[node]["tag"]
            if label not in correct_per_label:
                correct_per_label[label] = {"correct_labeled": 0, "correct_unlabeled": 0}
            if edge_is_correct(gold_graph, predicted_graph, gold_graph[node]["id"], exclude_ellipsis, ellipsis_only):
                correct_unlabeled += 1
                correct_per_label[label]["correct_unlabeled"] += 1
                if label_is_correct(gold_graph, predicted_graph, gold_graph[node]["id"], exclude_ellipsis, ellipsis_only):
                    correct_labeled += 1
                    correct_per_label[label]["correct_labeled"] += 1
            else: # ERROR ANALYSIS
                if len(gold_graph[node]["ellipsed_parents"]) > 0 and ellipsis_only == True:
                    if node in predicted_graph and len(predicted_graph[node]["ellipsed_parents"]) > 0:
                        print(" ".join([gold_graph[w]["text"] for w in gold_graph if gold_graph[w]["text"] != ""]), node)

    print(ellipsis_only)
    print(gold_nodes, predicted_nodes)
    print(correct_unlabeled)

    # I WILL MAKE THIS PART MORE READABLE LATER :D
    scores = {}
    scores["unlabeled_p"] = correct_unlabeled / predicted_nodes
    scores["unlabeled_r"] = correct_unlabeled / gold_nodes
    if scores["unlabeled_p"] + scores["unlabeled_r"] != 0:
        scores["unlabeled_f"] = 2 * ((scores["unlabeled_p"] * scores["unlabeled_r"]) / (scores["unlabeled_p"] + scores["unlabeled_r"]))
    scores["labeled_p"] = correct_labeled / predicted_nodes
    scores["labeled_r"] = correct_labeled / gold_nodes
    if scores["labeled_p"] + scores["labeled_r"] != 0:
        scores["labeled_f"] = 2 * ((scores["labeled_p"] * scores["labeled_r"]) / (scores["labeled_p"] + scores["labeled_r"]))
#    scores["per_label"] = {}
    # MODIFY CODE BELOW TO HANDLE DIVISION BY ZERO
#    for label in correct_per_label:
#        scores["per_label"][label] = {}
#        scores["per_label"][label]["unlabeled_p"] = correct_per_label[label]["correct_unlabeled"] / predicted_per_label[label]
#        scores["per_label"][label]["unlabeled_r"] = correct_per_label[label]["correct_unlabeled"] / gold_per_label[label]
#        if scores["per_label"][label]["unlabeled_p"] + scores["per_label"][label]["unlabeled_r"] != 0:
#            scores["per_label"][label]["unlabeled_f"] = 2 * ((scores["per_label"][label]["unlabeled_p"] * scores["per_label"][label]["unlabeled_r"]) / (scores["per_label"][label]["unlabeled_p"] + scores["per_label"][label]["unlabeled_r"]))
#        scores["per_label"][label]["labeled_p"] = correct_per_label[label]["correct_labeled"] / predicted_per_label[label]
#        scores["per_label"][label]["labeled_r"] = correct_per_label[label]["correct_labeled"] / gold_per_label[label]
#        if scores["per_label"][label]["labeled_p"] + scores["per_label"][label]["labeled_r"] != 0:
#            scores["per_label"][label]["labeled_f"] = 2 * ((scores["per_label"][label]["labeled_p"] * scores["per_label"][label]["labeled_r"]) / (scores["per_label"][label]["labeled_p"] + scores["per_label"][label]["labeled_r"]))

    return scores


def print_scores(scores_list):
    """
    Print scores in a pretty table.
    """

    table = []
    column_headers = ["",]
    rows = []
    for scores in scores_list:
        for row_header in scores:
            for column_header in scores[row_header]:
                column_headers.append(column_header)
        break
    for scores in scores_list:
        for row_header in scores:
            row = [row_header,]
            for column_header in scores[row_header]:
                row.append(round(scores[row_header][column_header], 4)) 
            rows.append(row)

    print(tabulate(rows, headers=column_headers, tablefmt="github"))


def main(
    gold_file: Path, 
    predicted_file: Path, 
    ):

    gold_graphs = get_graphs(gold_file)
    predicted_graphs = get_graphs(predicted_file)

    scores_all_edges = {"all_edges": score(gold_graphs, predicted_graphs)}
    scores_non_ellipsed_edges = {"non_ellipsed_edges": score(gold_graphs, predicted_graphs, exclude_ellipsis=True)}
    scores_ellipsed_edges = {"ellipsed_edges": score(gold_graphs, predicted_graphs, ellipsis_only=True)}

    print_scores([scores_all_edges, scores_non_ellipsed_edges, scores_ellipsed_edges])


if __name__ == "__main__":
    typer.run(main)