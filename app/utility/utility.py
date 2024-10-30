import os

def generate_media_path(media_type: str, order_id: str = None, product_id: str = None, 
                        detail_id: str = None, branch_number: str = None, 
                        generation_id: str = None, sequence_number: str = None) -> str:
    base_path = "files/"
    
    if media_type == "model_photo":
        return os.path.join(base_path, "model", f"{product_id}.jpg")
    elif media_type == "bgm_file":
        return os.path.join(base_path, "bgm", f"{product_id}")  # Adjust as necessary
    elif media_type == "original_photo":
        return os.path.join(base_path, "order", order_id, "original.jpg")
    elif media_type == "fixed_photo":
        return os.path.join(base_path, "order", order_id, "fixed.jpg")
    elif media_type == "merged_photo":
        return os.path.join(base_path, "order", order_id, "merge.jpg")
    elif media_type == "generated_video":
        return os.path.join(base_path, "order", order_id, detail_id, branch_number, "step1", f"{generation_id}-{sequence_number}.mp4")
    elif media_type == "face_corrected_video":
        return os.path.join(base_path, "order", order_id, detail_id, branch_number, "step2", f"{generation_id}-{sequence_number}.mp4")
    elif media_type == "final_video":
        return os.path.join(base_path, "order", order_id, detail_id, branch_number, "step3", f"{generation_id}-{sequence_number}.mp4")
    else:
        raise ValueError("Invalid media type")
