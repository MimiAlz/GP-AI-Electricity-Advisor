import dayjs from 'dayjs';

export const NILM_APPLIANCES = [
  { id: 'fridge', labelKey: 'appliance_fridge', color: '#1677ff' },
  { id: 'tv', labelKey: 'appliance_tv', color: '#13c2c2' },
  { id: 'washer', labelKey: 'appliance_washer', color: '#722ed1' },
  { id: 'dishwasher', labelKey: 'appliance_dishwasher', color: '#fa8c16' },
  { id: 'microwave', labelKey: 'appliance_microwave', color: '#eb2f96' },
  { id: 'kettle', labelKey: 'appliance_kettle', color: '#52c41a' },
];

function createSeed(value) {
  let seed = 0;
  for (let index = 0; index < value.length; index += 1) {
    seed = ((seed * 31) + value.charCodeAt(index)) >>> 0;
  }
  return seed || 1;
}

function createRandom(seedValue) {
  let seed = seedValue >>> 0;
  return () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function hourlyUsageForAppliance(applianceId, hour, dayOfWeek, random) {
  const morningPeak = hour >= 6 && hour <= 9;
  const lunchPeak = hour >= 12 && hour <= 14;
  const eveningPeak = hour >= 18 && hour <= 22;
  const weekend = dayOfWeek === 5 || dayOfWeek === 6;

  switch (applianceId) {
    case 'fridge':
      return 0.08 + random() * 0.03;
    case 'tv':
      return eveningPeak ? 0.18 + random() * 0.22 : 0.02 + random() * 0.04;
    case 'washer':
      return (weekend && hour >= 10 && hour <= 13) || (!weekend && hour >= 19 && hour <= 21)
        ? 0.15 + random() * 0.55
        : random() * 0.015;
    case 'dishwasher':
      return eveningPeak ? 0.12 + random() * 0.32 : random() * 0.02;
    case 'microwave':
      return morningPeak || lunchPeak || eveningPeak
        ? 0.06 + random() * 0.18
        : random() * 0.01;
    case 'kettle':
      return morningPeak || eveningPeak
        ? 0.08 + random() * 0.22
        : random() * 0.01;
    default:
      return random() * 0.03;
  }
}

export function buildNilmDataset(houseId, monthValue) {
  const month = dayjs(monthValue).startOf('month');
  const daysInMonth = month.daysInMonth();
  const random = createRandom(createSeed(`${houseId}-${month.format('YYYY-MM')}`));

  const dailySeries = {};
  const monthlyTotals = {};
  const hourlyAverages = {};
  const aggregateDaily = [];

  NILM_APPLIANCES.forEach(({ id }) => {
    dailySeries[id] = [];
    monthlyTotals[id] = 0;
    hourlyAverages[id] = Array.from({ length: 24 }, () => 0);
  });

  for (let dayIndex = 0; dayIndex < daysInMonth; dayIndex += 1) {
    const currentDay = month.add(dayIndex, 'day');
    const weekday = currentDay.day();
    let aggregateDay = 0;

    NILM_APPLIANCES.forEach(({ id }) => {
      let total = 0;

      for (let hour = 0; hour < 24; hour += 1) {
        const seasonality = 0.96 + ((currentDay.date() / daysInMonth) * 0.1);
        const value = clamp(hourlyUsageForAppliance(id, hour, weekday, random) * seasonality, 0, 1.6);
        total += value;
        hourlyAverages[id][hour] += value;
      }

      const roundedTotal = Number(total.toFixed(3));
      dailySeries[id].push({
        day: currentDay.format('MMM D'),
        isoDate: currentDay.format('YYYY-MM-DD'),
        value: roundedTotal,
      });
      monthlyTotals[id] += roundedTotal;
      aggregateDay += roundedTotal;
    });

    aggregateDaily.push({
      day: currentDay.format('MMM D'),
      isoDate: currentDay.format('YYYY-MM-DD'),
      value: Number(aggregateDay.toFixed(3)),
    });
  }

  Object.keys(hourlyAverages).forEach((applianceId) => {
    hourlyAverages[applianceId] = hourlyAverages[applianceId].map((value) => Number((value / daysInMonth).toFixed(3)));
  });

  const ranking = NILM_APPLIANCES
    .map((appliance) => ({
      ...appliance,
      total: Number(monthlyTotals[appliance.id].toFixed(2)),
      share: 0,
    }))
    .sort((left, right) => right.total - left.total);

  const totalUsage = Number(ranking.reduce((sum, item) => sum + item.total, 0).toFixed(2));
  ranking.forEach((item) => {
    item.share = totalUsage > 0 ? Number(((item.total / totalUsage) * 100).toFixed(1)) : 0;
  });

  const peakDay = [...aggregateDaily].sort((left, right) => right.value - left.value)[0] || null;

  return {
    monthLabel: month.format('MMMM YYYY'),
    totalUsage,
    peakDay,
    aggregateDaily,
    dailySeries,
    ranking,
    hourlyAverages,
  };
}