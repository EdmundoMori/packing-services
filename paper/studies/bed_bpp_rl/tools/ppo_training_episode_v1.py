"""Episode audit wrapper with explicit training-order provenance."""
from environment import ENVIRONMENT_VERSION,ENGINE_REQUIRED_COMMIT
from corpus_writer import EpisodeRecorder
from ppo_episode_audit_v1 import AuditedEnv

class TrainingAuditedEnv(AuditedEnv):
    def reset_order(self,problem,*,order_id,target_id,decision_budget=None):
        if self.recorder is not None and not (self.env.summary.terminated or self.env.summary.truncated):
            raise ValueError('Cannot reset open training episode')
        self.number+=1
        self.recorder=EpisodeRecorder(episode_id=f'seed_{self.seed}_episode_{self.number:05d}',
            order_id=order_id,target_id=target_id,environment_version=ENVIRONMENT_VERSION,
            engine_commit=ENGINE_REQUIRED_COMMIT,behavior_policy='ppo_online_policy_versions',behavior_seed=self.seed)
        self.observation,self.info=self.env.reset(problem,decision_budget=decision_budget)
        if self.info['terminated'] or self.info['truncated']:self.persist_prefix()
        return self.observation,self.info
