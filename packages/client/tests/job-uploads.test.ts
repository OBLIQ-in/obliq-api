import { describe, expect, it, vi } from "vitest";
import { JobsResource } from "../src/resources/jobs.js";
import type { CreateJobOptions } from "../src/types.js";

async function getUploadedFile(options: CreateJobOptions): Promise<File> {
  const request = vi.fn(async (_path: string, _init?: RequestInit) =>
    Response.json({ id: "test-job", status: "queued" }),
  );
  await new JobsResource(request).create(options);
  const [, init] = request.mock.calls[0];
  return (init!.body as FormData).get("file") as File;
}

describe("multipart job uploads", () => {
  it("names an unnamed byte payload and sends only its selected bytes", async () => {
    const bytes = new Uint8Array([0, 1, 2, 3, 4]).subarray(1, 4);
    const file = await getUploadedFile({ file: bytes });
    expect(file.name).toBe("document.pdf");
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(bytes);
  });

  it("combines stream chunks without including bytes outside their views", async () => {
    const bytes = new Uint8Array([0, 1, 2, 3, 4]);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.subarray(1, 3));
        controller.enqueue(bytes.subarray(3, 4));
        controller.close();
      },
    });
    const file = await getUploadedFile({ file: stream });
    expect(file.name).toBe("document.pdf");
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(bytes.subarray(1, 4));
  });

  it("keeps a File's name unless the caller provides another", async () => {
    // FormData can return a File even when the runtime has no global File constructor.
    const form = new FormData();
    form.append("file", new Blob(["synthetic"], { type: "image/png" }), "scan.png");
    const source = form.get("file") as File;
    expect((await getUploadedFile({ file: source })).name).toBe("scan.png");
    expect((await getUploadedFile({ file: source, fileName: "override.png" })).name).toBe("override.png");
  });
});
