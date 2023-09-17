from __future__ import division

import math
import random
import time
import copy
from multiprocessing import Process, Queue, Manager
from multiprocessing import Pool
from multiprocessing.managers import BaseManager, NamespaceProxy

from mcts.base.base import BaseState


def random_policy(state: BaseState) -> float:
    while not state.is_terminal():
        try:
            action = random.choice(state.get_possible_actions())
        except IndexError:
            raise Exception("Non-terminal state has no possible actions: " + str(state))
        state = state.take_action(action)
    return state.get_reward()


# -- this fails: sometimes the .join() will hang
# - this is potential due to the Queue. -> Using Process() directly without
# using Queue instead (seems to be a tiny bit slower tho..)
class RolloutProcess(Process):
    def __init__(self, queue, rollout_policy):
        self.queue = queue
        self.rollout_policy = rollout_policy
        super().__init__()
        
    def run(self):
        while not self.queue.empty():
            inputs = self.queue.get()
            input_id = inputs[0]
            state = inputs[1]
            return_dict = inputs[2]
            reward = self.rollout_policy(state)
            return_dict[input_id] = reward


class TreeNodeProxy(NamespaceProxy):
    _exposed_ = ('__getattribute__', '__setattr__', '__delattr__',
                 'all_child_have_at_least_one_visit', 'add_child')

    def all_child_have_at_least_one_visit(self):
        callmethod = object.__getattribute__(self, '_callmethod')
        return callmethod('all_child_have_at_least_one_visit')
    #TODO: need debug
    def add_child(self, action, node):
        callmethod = object.__getattribute__(self, '_callmethod')
        #print(callmethod)
        return callmethod('add_child', args=(action, node))



class TreeNode:
    def __init__(self, state, parent):
        self.state = state
        self.is_terminal = state.is_terminal()
        self.is_fully_expanded = self.is_terminal
        self.all_child_have_been_explored = False
        self.parent = parent
        self.numVisits = 0
        self.totalReward = 0
        self.children = {}

    def all_child_have_at_least_one_visit(self,) -> bool:
        if not self.all_child_have_been_explored:
            if len(self.children) > 0:
                self.all_child_have_been_explored = all([child.numVisits>0 for child in self.children.values()])
            else: return False
        return self.all_child_have_been_explored

    def __str__(self):
        s = ["totalReward: %s" % self.totalReward,
             "numVisits: %d" % self.numVisits,
             "isTerminal: %s" % self.is_terminal,
             "possibleActions: %s" % (self.children.keys())]
        return "%s: {%s}" % (self.__class__.__name__, ', '.join(s))


class MCTS:
    def __init__(self,
                 time_limit: int = None,
                 timeLimit=None,
                 iteration_limit: int = None,
                 iterationLimit=None,
                 exploration_constant: float = None,
                 explorationConstant=math.sqrt(2),
                 rollout_policy=None,
                 rolloutPolicy=random_policy):
        # backwards compatibility
        time_limit = timeLimit if time_limit is None else time_limit
        iteration_limit = iterationLimit if iteration_limit is None else iteration_limit
        exploration_constant = explorationConstant if exploration_constant is None else exploration_constant
        rollout_policy = rolloutPolicy if rollout_policy is None else rollout_policy

        self.root = None
        if time_limit is not None:
            if iteration_limit is not None:
                raise ValueError("Cannot have both a time limit and an iteration limit")
            # time taken for each MCTS search in milliseconds
            self.timeLimit = time_limit
            self.limit_type = 'time'
        else:
            if iteration_limit is None:
                raise ValueError("Must have either a time limit or an iteration limit")
            # number of iterations of the search
            if iteration_limit < 1:
                raise ValueError("Iteration limit must be greater than one")
            self.search_limit = iteration_limit
            self.limit_type = 'iterations'
        self.exploration_constant = exploration_constant
        self.rollout_policy = rollout_policy

    def search(self, initialState: BaseState = None, initial_state: BaseState = None, needDetails: bool = False,
               need_details: bool = None):
        initial_state = initialState if initial_state is None else initial_state
        need_details = needDetails if need_details is None else need_details
        self.root = TreeNode(initial_state, None)

        if self.limit_type == 'time':
            time_limit = time.time() + self.timeLimit / 1000
            while time.time() < time_limit:
                self.execute_round()
        else:
            for i in range(self.search_limit):
                self.execute_round()

        best_child = self.get_best_child(self.root, 0)
        action = (action for action, node in self.root.children.items() if node is best_child).__next__()
        if need_details:
            return action, best_child.totalReward / best_child.numVisits
        else:
            return action


    def search_parallel(self, initialState: BaseState = None, initial_state: BaseState = None, needDetails: bool = False,
                        need_details: bool = None, n_jobs: int = 1):
        initial_state = initialState if initial_state is None else initial_state
        need_details = needDetails if need_details is None else need_details
        self.root = TreeNode(initial_state, None)

        if self.limit_type == 'time':
            raise NotImplementedError("Cannot use search parallel with time limit type")
        
        manager = Manager()
        BaseManager.register('TreeNode', TreeNode, TreeNodeProxy)
        basemanager = BaseManager()
        basemanager.start()
        root_shared = basemanager.TreeNode(initial_state, None)

        #import pdb; pdb.set_trace()
        
        for _ in range(0, self.search_limit, n_jobs):
            
            input_nodes = []
            processes = []
            return_dict = manager.dict()
            
            for index in range(n_jobs):
                tmp_node = self.select_node(self.root)
                input_nodes.append(tmp_node)
                processes.append(Process(target=self.execute_rollout_parallel,args=(index, tmp_node.state, return_dict)))
                #processes.append(Process(target=self.execute_rollout_parallel,args=(index,root_shared,return_dict)))
            
            for p in processes: p.start()
            
            for p in processes: p.join()
            
            for index, reward in return_dict.items():
            #for index, rez in return_dict.items():
                self.backpropogate(input_nodes[index], reward)
                #node, reward = rez
                #self.backpropogate(node, reward)
            
        best_child = self.get_best_child(self.root, 0)
        #best_child = self.get_best_child(root_shared, 0)
        action = (action for action, node in self.root.children.items() if node is best_child).__next__()
        #action = (action for action, node in root_shared.children.items() if node is best_child).__next__()
        if need_details:
            return action, best_child.totalReward / best_child.numVisits
        else:
            return action
    
    def execute_rollout_parallel(self, input_id, state, return_dict):
    #def execute_rollout_parallel(self, input_id, root, return_dict):
        #node = self.select_node(root)
        reward = self.rollout_policy(state)
        return_dict[input_id] = reward

    def execute_round(self):
        """
            execute a selection-expansion-simulation-backpropagation round
        """
        node = self.select_node(self.root)
        reward = self.rollout_policy(node.state)
        self.backpropogate(node, reward)

    def select_node(self, node: TreeNode) -> TreeNode:
        while not node.is_terminal:
            if node.is_fully_expanded:
                if node.all_child_have_at_least_one_visit():
                    node = self.get_best_child(node, self.exploration_constant)
                else:
                    node = self.get_random_child(node)
            else:
                return self.expand(node)
        return node

    def expand(self, node: TreeNode) -> TreeNode:
        actions = node.state.get_possible_actions()
        for action in actions:
            if action not in node.children:
                newNode = TreeNode(node.state.take_action(action), node)
                node.children[action] = newNode
                if len(actions) == len(node.children):
                    node.is_fully_expanded = True
                return newNode

        raise Exception("Should never reach here")

    def backpropogate(self, node: TreeNode, reward: float):
        while node is not None:
            node.numVisits += 1
            node.totalReward += reward
            node = node.parent

    def get_best_child(self, node: TreeNode, explorationValue: float, exploration_value: float = None) -> TreeNode:
        exploration_value = explorationValue if exploration_value is None else exploration_value
        best_value = float("-inf")
        best_nodes = []
        for child in node.children.values():
            node_value = (node.state.get_current_player() * child.totalReward / child.numVisits +
                          exploration_value * math.sqrt(math.log(node.numVisits) / child.numVisits))
            if node_value > best_value:
                best_value = node_value
                best_nodes = [child]
            elif node_value == best_value:
                best_nodes.append(child)
        return random.choice(best_nodes)

    def get_random_child(self, node: TreeNode) -> TreeNode:
        return random.choice(list(node.children.values()))

