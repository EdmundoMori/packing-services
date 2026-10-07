"""Audit channel around the public RL environment, separate from actor input.

Open-prefix snapshots are not closed corpus episodes. No retrospective
truncation is invented at rollout boundaries or when a process is killed.
"""
import copy
from pathlib import Path
from environment import BedBppRlEnv, ENVIRONMENT_VERSION, ENGINE_REQUIRED_COMMIT
from corpus_writer import EpisodeRecorder
from episode_export import build_episode_artifacts
from artifact_contrast import contrast_artifacts
from resource_verifier import verify_episode_document
from ppo_rollout_v1 import save_record


class AuditedEnv:
    def __init__(self, root, *, seed):
        self.env = BedBppRlEnv()
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.seed = seed; self.number = 0; self.recorder = None
        self.closed_episodes = 0; self.prefixes = 0
        self.observation = None; self.info = None

    def reset(self, problem, *, decision_budget=None):
        if self.recorder is not None and not (self.env.summary.terminated or self.env.summary.truncated):
            raise ValueError('Cannot reset an open audited episode')
        self.number += 1
        self.recorder = EpisodeRecorder(episode_id=f'synthetic_{self.number:04d}',
            order_id='synthetic', target_id='synthetic',
            environment_version=ENVIRONMENT_VERSION, engine_commit=ENGINE_REQUIRED_COMMIT,
            behavior_policy='ppo_online_policy_versions', behavior_seed=self.seed)
        self.observation, self.info = self.env.reset(problem, decision_budget=decision_budget)
        if self.info['terminated'] or self.info['truncated']: self.persist_prefix()
        return self.observation, self.info

    def step(self, action):
        before = copy.deepcopy(self.info)
        previous = list(self.observation)
        nxt, reward, term, trunc, info = self.env.step(action)
        if info.get('placed') is not True:
            raise ValueError('No fabricated transition in audited PPO')
        proposals = before['proposals']
        self.recorder.add_step(observation=previous, observation_next=nxt, action=action,
            action_mask=before['action_mask'], action_mask_next=info['action_mask'],
            reward=reward, rule_proposals=proposals, chosen_geometry=proposals[action]['geometry'])
        self.observation = list(nxt); self.info = dict(info)
        return nxt, reward, term, trunc, info

    def persist_prefix(self):
        artifacts = build_episode_artifacts(self.env, self.env.problem)
        closed = self.env.summary.terminated or self.env.summary.truncated
        self.recorder.set_artifacts(artifacts)
        if closed:
            document = self.recorder.close(terminated=self.env.summary.terminated,
                truncated=self.env.summary.truncated, end_reason=self.env.summary.end_reason,
                summary=self.env.summary.as_dict())
            report = verify_episode_document(document, require_complete=True)
            if report.get('complete_verification') is not True:
                raise ValueError('Closed episode lacks complete audit')
            self.closed_episodes += 1
        else:
            document = dict(kind='ppo_open_prefix_audit_v1',
                episode_id=self.recorder.episode_id, transitions=copy.deepcopy(self.recorder._rows),
                n_transitions=len(self.recorder._rows), artifacts=artifacts,
                terminated=False, truncated=False, end_reason=None,
                summary=self.env.summary.as_dict(), physical_stability_verified=None)
            # Geometry/identity/volume contrast, not structural validation of a
            # closed episode. Keep the prefix explicitly open.
            report = contrast_artifacts(document)
            if report.get('ok') is not True: raise ValueError('Prefix geometry audit failed')
        name = f'{self.recorder.episode_id}_prefix_{len(self.recorder._rows):04d}'
        save_record(self.root/(name+'.json'), document)
        save_record(self.root/(name+'.audit.json'), report)
        self.prefixes += 1
        return name

    def close(self):
        self.env.close()


def verify_episode_audits(root):
    prefixes = 0; closed = 0; rows = {}
    for path in sorted(Path(root).glob('*_prefix_*.json')):
        if path.name.endswith('.audit.json'): continue
        import json
        document = json.loads(path.read_text())
        if document.get('kind') == 'ppo_open_prefix_audit_v1':
            if document['terminated'] or document['truncated']: raise ValueError('Open prefix flags')
            report = contrast_artifacts(document)
            if report.get('ok') is not True: raise ValueError('Prefix audit failure')
        else:
            report = verify_episode_document(document, require_complete=True)
            if report.get('complete_verification') is not True: raise ValueError('Closed audit failure')
            closed += 1
        prefixes += 1
        # Prefixes overlap; unique episode+step identities avoid double counting.
        for index, row in enumerate(document['transitions']):
            key = (document['episode_id'], index)
            if key in rows:
                fields = ('observation','observation_next','action','reward','chosen_geometry')
                if any(rows[key][k] != row[k] for k in fields): raise ValueError('Conflicting prefix')
            rows[key] = row
    return dict(prefixes=prefixes, closed_episodes=closed,
        unique_transitions=len(rows), physical_stability_verified=None)
