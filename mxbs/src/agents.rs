use crate::{Cell, DreamResult, FACTOR_DIM, MxBS, MxBSError, SearchResult};
use std::collections::HashMap;

#[derive(Clone)]
pub struct AgentRegistry {
    agents: Vec<(String, String, u64, u32)>, // (id, name, bit, owner_id)
    id_to_index: HashMap<String, usize>,
    all_bits: u64,
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl AgentRegistry {
    pub fn new() -> Self {
        Self {
            agents: Vec::new(),
            id_to_index: HashMap::new(),
            all_bits: 0,
        }
    }

    pub fn register(&mut self, id: &str, name: &str) -> Result<u64, MxBSError> {
        let index = self.agents.len();
        if index >= 64 {
            return Err(MxBSError::TooManyAgents);
        }
        let bit = 1u64 << index;
        let owner_id = index as u32;
        self.agents
            .push((id.to_string(), name.to_string(), bit, owner_id));
        self.id_to_index.insert(id.to_string(), index);
        self.all_bits |= bit;
        Ok(bit)
    }

    pub fn bit(&self, id: &str) -> Option<u64> {
        self.id_to_index.get(id).map(|&i| self.agents[i].2)
    }

    pub fn owner_id(&self, id: &str) -> Option<u32> {
        self.id_to_index.get(id).map(|&i| self.agents[i].3)
    }

    pub fn all_bits(&self) -> u64 {
        self.all_bits
    }

    pub fn count(&self) -> usize {
        self.agents.len()
    }

    pub fn store_public(
        &self,
        mxbs: &MxBS,
        turn: u32,
        agent_id: &str,
        text: &str,
        features: [u8; FACTOR_DIM],
        price: u8,
    ) -> Result<u64, MxBSError> {
        let owner = self
            .owner_id(agent_id)
            .ok_or_else(|| MxBSError::AgentNotFound(agent_id.to_string()))?;
        mxbs.store(
            Cell::new(owner, text)
                .turn(turn)
                .group_bits(self.all_bits)
                .mode(0o744)
                .price(price)
                .features(features),
        )
    }

    pub fn store_private(
        &self,
        mxbs: &MxBS,
        turn: u32,
        agent_id: &str,
        text: &str,
        features: [u8; FACTOR_DIM],
        price: u8,
    ) -> Result<u64, MxBSError> {
        let owner = self
            .owner_id(agent_id)
            .ok_or_else(|| MxBSError::AgentNotFound(agent_id.to_string()))?;
        let bit = self.bit(agent_id).unwrap();
        mxbs.store(
            Cell::new(owner, text)
                .turn(turn)
                .group_bits(bit)
                .mode(0o700)
                .price(price)
                .features(features),
        )
    }

    pub fn search(
        &self,
        mxbs: &MxBS,
        agent_id: &str,
        query: [u8; FACTOR_DIM],
        current_turn: u32,
    ) -> Result<Vec<SearchResult>, MxBSError> {
        let owner = self
            .owner_id(agent_id)
            .ok_or_else(|| MxBSError::AgentNotFound(agent_id.to_string()))?;
        let bit = self.bit(agent_id).unwrap();
        mxbs.search(query, owner, bit)
            .current_turn(current_turn)
            .exec()
    }

    pub fn dream(
        &self,
        mxbs: &MxBS,
        agent_id: &str,
        current_turn: u32,
    ) -> Result<Vec<DreamResult>, MxBSError> {
        let owner = self
            .owner_id(agent_id)
            .ok_or_else(|| MxBSError::AgentNotFound(agent_id.to_string()))?;
        let bit = self.bit(agent_id).unwrap();
        mxbs.dream(owner, bit).current_turn(current_turn).exec()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{FACTOR_DIM, MxBS, MxBSConfig};

    #[test]
    fn test_agent_registry_basics() {
        let mut reg = AgentRegistry::new();
        let bit0 = reg.register("teson", "テソン").unwrap();
        let bit1 = reg.register("jihun", "ジフン").unwrap();
        assert_eq!(bit0, 1);
        assert_eq!(bit1, 2);
        assert_eq!(reg.all_bits(), 3);
        assert_eq!(reg.count(), 2);
        assert_eq!(reg.owner_id("teson"), Some(0));
        assert_eq!(reg.owner_id("jihun"), Some(1));
    }

    #[test]
    fn test_agent_store_and_search() {
        let mut reg = AgentRegistry::new();
        reg.register("teson", "テソン").unwrap();
        reg.register("jihun", "ジフン").unwrap();

        let mxbs = MxBS::open(":memory:", MxBSConfig::default()).unwrap();
        let f = [100; FACTOR_DIM];

        reg.store_public(&mxbs, 1, "teson", "公開情報", f, 80)
            .unwrap();
        reg.store_private(&mxbs, 1, "teson", "内なる声", f, 120)
            .unwrap();

        let results = reg.search(&mxbs, "teson", f, 1).unwrap();
        assert_eq!(results.len(), 2);

        let results = reg.search(&mxbs, "jihun", f, 1).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].text, "公開情報");
    }

    #[test]
    fn test_agent_not_found() {
        let reg = AgentRegistry::new();
        let mxbs = MxBS::open(":memory:", MxBSConfig::default()).unwrap();
        assert!(
            reg.store_public(&mxbs, 1, "nobody", "test", [0; FACTOR_DIM], 80)
                .is_err()
        );
    }
}
