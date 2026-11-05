function success(): number { return 1; }
function failure(): number { return 0; }

export function settle(value: Promise<number>): Promise<number> {
  return value.then(
    () => success(),
    () => failure(),
  );
}

export function siblings(): Promise<number> {
  return Promise.resolve().then(() => success(), () => failure());
}

export function nested(): Promise<number> {
  return Promise.resolve().then(
    () => { function step(): number { return success(); } return step(); },
    () => { function step(): number { return failure(); } return step(); },
  );
}
