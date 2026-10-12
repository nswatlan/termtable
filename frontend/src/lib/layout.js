/**
 * Lay out overlapping blocks in a single day column side by side, the way
 * Google Calendar does. items need numeric `start` and `end` (minutes).
 * Returns new objects with `col` and `cols` added; each cluster of
 * transitively-overlapping items shares the same `cols`.
 */
export function layoutOverlaps(items) {
  const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end);
  const result = [];
  let cluster = [];
  let columns = []; // end time of the last item in each column
  let clusterEnd = -Infinity;

  const flush = () => {
    for (const item of cluster) item.cols = columns.length;
    result.push(...cluster);
    cluster = [];
    columns = [];
  };

  for (const original of sorted) {
    const item = { ...original };
    if (item.start >= clusterEnd) flush();
    let col = columns.findIndex((end) => end <= item.start);
    if (col === -1) {
      col = columns.length;
      columns.push(item.end);
    } else {
      columns[col] = item.end;
    }
    item.col = col;
    cluster.push(item);
    clusterEnd = Math.max(clusterEnd, item.end);
  }
  flush();
  return result;
}
