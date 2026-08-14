import gradio as gr
import spaces
import torch


@spaces.GPU(duration=60)
def check_gpu():
    if not torch.cuda.is_available():
        return {
            "status": "error",
            "gpu": None,
            "message": "CUDA GPU was not allocated",
        }

    return {
        "status": "ok",
        "gpu": torch.cuda.get_device_name(0),
        "pytorch": torch.__version__,
        "cuda": torch.version.cuda,
    }


demo = gr.Interface(
    fn=check_gpu,
    inputs=[],
    outputs=gr.JSON(label="Ashes Worker Status"),
    title="Ashes GPU Worker",
    description="ZeroGPU infrastructure test for the Ashes 3D Commerce Engine.",
    submit_btn="Test Cloud GPU",
)

demo.launch()
