import '@databricks/appkit-ui/react';
import type { SQLBooleanMarker, SQLDateMarker, SQLNumberMarker, SQLTimestampMarker, SQLStringMarker } from '@databricks/appkit-ui/js';

declare module '@databricks/appkit-ui/react' {
  interface QueryRegistry {
    executive_kpis: {
      parameters: Record<string, never>;
      result: Array<{
        score_date: SQLDateMarker; student_count: SQLNumberMarker; at_risk_count: SQLNumberMarker;
        retention_rate: SQLNumberMarker; intervention_coverage: SQLNumberMarker;
        time_to_first_intervention_days: SQLNumberMarker; follow_up_completion_rate: SQLNumberMarker;
        estimated_next_term_net_tuition_exposure: SQLNumberMarker; data_freshness_at: SQLTimestampMarker;
      }>;
    };
    executive_trends: {
      parameters: Record<string, never>;
      result: Array<{ score_date: SQLDateMarker; risk_tier: SQLStringMarker; student_count: SQLNumberMarker; average_risk_score: SQLNumberMarker }>;
    };
    advisor_caseload: {
      parameters: { riskTier: SQLStringMarker; pageSize: SQLNumberMarker; pageOffset: SQLNumberMarker };
      result: Array<{ student_id: SQLStringMarker; advisor_id: SQLStringMarker; program_code: SQLStringMarker; risk_score: SQLNumberMarker; risk_tier: SQLStringMarker; intervention_status: SQLStringMarker; caseload_priority: SQLNumberMarker; follow_up_due: SQLBooleanMarker; leading_factors: SQLStringMarker; total_count: SQLNumberMarker }>;
    };
    student_detail: {
      parameters: { studentId: SQLStringMarker };
      result: Array<{ student_id: SQLStringMarker; advisor_id: SQLStringMarker; program_code: SQLStringMarker; risk_score: SQLNumberMarker; risk_tier: SQLStringMarker; attendance_rate_28d: SQLNumberMarker; missed_assignments_28d: SQLNumberMarker; leading_factors: SQLStringMarker }>;
    };
  }
}
