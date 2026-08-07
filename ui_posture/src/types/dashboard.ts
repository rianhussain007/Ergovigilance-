// Re-export from centralized API types for backward compatibility.
// New code should import directly from '@/src/types/api'.
export type {
  RiskLevel,
  StatusType,
  FeatureStatus,
  TrendDirection,
  TabId,
  SessionInfo,
  LiveStatus,
  ErgonomicFeature,
  Issue,
  Recommendations,
  SessionAnalytics,
  RiskDataPoint,
  TrendAnalysis,
  DashboardResponse as DashboardData,
  SessionRecord,
  WeeklyTrend,
  FeatureTrend,
  RiskDistribution,
} from './api';
