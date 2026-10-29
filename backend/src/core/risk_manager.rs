use crate::models::battery::BatteryConfig;
use crate::models::order::{OrderSide, OrderSubmitRequest, RiskCheckResult};
use std::sync::atomic::{AtomicBool, Ordering};

pub struct RiskManager {
    pub kill_switch_active: AtomicBool,
}

impl Default for RiskManager {
    fn default() -> Self {
        Self {
            kill_switch_active: AtomicBool::new(false),
        }
    }
}

impl RiskManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_kill_switch_active(&self) -> bool {
        self.kill_switch_active.load(Ordering::SeqCst)
    }

    pub fn set_kill_switch(&self, active: bool) {
        self.kill_switch_active.store(active, Ordering::SeqCst);
    }

    pub fn validate_order(
        &self,
        request: &OrderSubmitRequest,
        config: &BatteryConfig,
        current_soc: f64,
    ) -> RiskCheckResult {
        let mut reasons = Vec::new();

        // 1. Check Kill-Switch
        if self.is_kill_switch_active() {
            reasons
                .push("Emergency Kill-Switch is ACTIVE. All trading orders rejected.".to_string());
            return RiskCheckResult {
                passed: false,
                reasons,
            };
        }

        // 2. Check Power Rating
        if request.power_mw <= 0.0 {
            reasons.push("Order power must be greater than 0 MW.".to_string());
        }

        if request.power_mw > config.power_mw + 1e-3 {
            reasons.push(format!(
                "Requested power {:.1} MW exceeds inverter physical rating of {:.1} MW.",
                request.power_mw, config.power_mw
            ));
        }

        // 3. Check SoC Envelope
        match request.side {
            OrderSide::Charge => {
                if current_soc >= config.soc_max - 0.01 {
                    reasons.push(format!(
                        "Battery SoC ({:.1}%) is already at or above maximum operating limit ({:.1}%). Charging prohibited.",
                        current_soc * 100.0,
                        config.soc_max * 100.0
                    ));
                }
            }
            OrderSide::Discharge => {
                if current_soc <= config.soc_min + 0.01 {
                    reasons.push(format!(
                        "Battery SoC ({:.1}%) is already at or below minimum operating reserve ({:.1}%). Discharging prohibited.",
                        current_soc * 100.0,
                        config.soc_min * 100.0
                    ));
                }
            }
            OrderSide::Idle => {}
        }

        RiskCheckResult {
            passed: reasons.is_empty(),
            reasons,
        }
    }
}
