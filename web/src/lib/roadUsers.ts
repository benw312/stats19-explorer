/** Display names for mart.road_user_group values. */
export const ROAD_USER_GROUP_LABEL: Record<string, string> = {
  pedestrian: 'Pedestrian',
  pedal_cycle: 'Pedal cycle',
  motorcycle: 'Motorcycle',
  car: 'Car / taxi',
  bus: 'Bus / minibus',
  goods_light: 'Van (≤ 3.5 t)',
  goods_heavy: 'HGV (> 3.5 t)',
  goods_unknown: 'Goods (weight unknown)',
  ppt: 'E-scooter / PPT',
  mobility_scooter: 'Mobility scooter',
  horse: 'Ridden horse',
  other: 'Other vehicle',
  unknown: 'Unknown',
}

export const roadUserLabel = (group: string): string => ROAD_USER_GROUP_LABEL[group] ?? group
