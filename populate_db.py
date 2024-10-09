import os
import random
import time
import json
import re
import sqlite3
from datetime import datetime, timedelta
from app import db, Post, Comment, Subllmit, User, app  # Ensure 'app' is correctly imported
from openai import OpenAI  # Import OpenAI client
import torch
from diffusers import StableDiffusionPipeline

# Path to your database
DB_NAME = "instance/llmit.db"

# Initialize OpenAI client
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Set environment variables before importing any dependent libraries
cache_directory = os.path.join(os.getcwd(), "huggingface")  # Use current working directory
os.environ['HF_HOME'] = cache_directory  # Alternatively, you can use 'TRANSFORMERS_CACHE'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = "max_split_size_mb:128"  # Helps with fragmentation

# Create cache directory if it doesn't exist
os.makedirs(cache_directory, exist_ok=True)

# Clear any existing GPU cache
torch.cuda.empty_cache()

# Initialize the device to GPU if available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Initialize the Stable Diffusion Pipeline
try:
    pipe = StableDiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-2-1",
        cache_dir=cache_directory,
        torch_dtype=torch.float16,
        revision="fp16"
    )
    pipe.to(device)
    print("Model loaded successfully.")
except Exception as e:
    print("An unexpected error occurred while loading the model:", e)
    exit(1)

# List of Subllmits
groups = [
    'announcements', 'Art', 'AskLLMit', 'askscience', 'atheism', 'aww', 'blog',
    'books', 'creepy', 'dataisbeautiful', 'DIY', 'Documentaries', 'EarthPorn',
    'explainlikeimfive', 'food', 'funny', 'Futurology', 'gadgets', 'gaming',
    'GetMotivated', 'history', 'IAmA', 'InternetIsBeautiful', 'Jokes',
    'LifeProTips', 'listentothis', 'mildlyinteresting', 'movies', 'Music', 'news',
    'nosleep', 'nottheonion', 'OldSchoolCool', 'personalfinance', 'philosophy',
    'photoshopbattles', 'pics', 'science', 'Showerthoughts', 'space', 'sports',
    'television', 'tifu', 'todayilearned', 'TwoXChromosomes', 'UpliftingNews',
    'videos', 'worldnews', 'WritingPrompts'
]

def extract_json(response_text):
    try:
        json_str = re.search(r'\{.*?\}', response_text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        print(f"Response text was: {response_text}")
        return None

def generate_image(image_prompt, post):
    try:
        image = pipe(prompt=image_prompt, guidance_scale=7.5, num_inference_steps=20, height=512, width=512).images[0]

        # Save the image with a unique filename
        image_filename = f"{post.group_name}_{post.id}_{random.randint(0, 100000)}.png"
        image_path = os.path.join('static', 'uploads', image_filename)  # Use relative path
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        image.save(image_path)

        # Update the post with the relative image URL
        image_url = f"/static/uploads/{image_filename}"
        post.image_url = image_url
        db.session.commit()

        print(f"Generated image for post {post.id}: {post.title}")

    except Exception as e:
        print(f"Error generating image for post {post.id}: {e}")

def generate_post_for_group(group_name, user_profile, post_count):
    try:
        prompt = (
            f"As a user named {user_profile['username']} with the following background: '{user_profile['background']}' and goal: '{user_profile['goal']}', "
            f"write a typical post for the '{group_name}' Subllmit that fits the theme of this Subllmit. "
            "Respond ONLY with a JSON object in the following format:\n"
            "{\n"
            '  "title": "Your post title",\n'
            '  "content": "Your post content (optional)",\n'
            '  "image_prompt": "A concise description for image generation (optional)"\n'
            "}\n"
        )

        completion = client.chat.completions.create(
            model="unsloth/Llama-3.2-3B-Instruct-GGUF",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )

        response_text = completion.choices[0].message.content.strip()
        print(f"AI Response: {response_text}")  # For debugging

        # Extract JSON from the response
        post_data = extract_json(response_text)
        if not post_data:
            print(f"Failed to extract JSON for group '{group_name}'. Skipping this post.")
            return None, None, None

        title = post_data.get('title', '').strip()
        content = post_data.get('content', '').strip()
        image_prompt = post_data.get('image_prompt', '').strip()

        # Create the post
        post = Post(
            group_name=group_name,
            title=title,
            content=content,
            image_url=None,  # Will be updated if an image is generated
            upvotes=random.randint(1, 1000),
            downvotes=random.randint(0, 500),
            is_ai_generated=True,
            timestamp=datetime.utcnow(),
            user_id=user_profile['id']  # Assign user_id here
        )
        db.session.add(post)
        db.session.commit()

        print(f"Generated AI post for {group_name}: {title}")

        # Generate an image for every 10th post
        if post_count % 10 == 0 and image_prompt:  # Use image prompt if exists
            generate_image(image_prompt, post)

        return post.id, title, image_prompt

    except Exception as e:
        print(f"Error generating post for {group_name}: {e}")
        return None, None, None

def generate_comment_for_post(post_id, post_title, group_name, user_profile):
    try:
        prompt = (
            f"As a user named {user_profile['username']}, write a comment in response to the post titled '{post_title}' in the '{group_name}' Subllmit on LLMit. "
            "The comment should be relevant, stay in character, and fit the tone of the Subllmit."
        )

        completion = client.chat.completions.create(
            model="unsloth/Llama-3.2-3B-Instruct-GGUF",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )

        comment_content = completion.choices[0].message.content.strip()
        print(f"AI Comment Response: {comment_content}")  # For debugging

        # Create the comment
        comment = Comment(
            post_id=post_id,
            content=comment_content,
            is_ai_generated=True,
            upvotes=random.randint(1, 100),
            downvotes=random.randint(0, 50),
            timestamp=datetime.utcnow(),
            user_id=user_profile['id']  # Assign user_id here
        )
        db.session.add(comment)
        db.session.commit()

        print(f"Generated AI comment for post {post_id}")

    except Exception as e:
        print(f"Error generating comment for post {post_id}: {e}")

def create_new_subllmit():
    try:
        prompt = (
            "Generate a unique and interesting Subllmit name for LLMit that does not already exist."
        )

        completion = client.chat.completions.create(
            model="unsloth/Llama-3.2-3B-Instruct-GGUF",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=10,
        )

        subllmit_name = completion.choices[0].message.content.strip()
        existing_subllmit = Subllmit.query.filter_by(name=subllmit_name).first()
        if existing_subllmit:
            print(f"Subllmit '{subllmit_name}' already exists.")
            return

        # Create new Subllmit
        new_subllmit = Subllmit(name=subllmit_name)
        db.session.add(new_subllmit)
        db.session.commit()
        print(f"Created new Subllmit: {subllmit_name}")

    except Exception as e:
        print(f"Error creating new Subllmit: {e}")

def fetch_bot_users():
    return User.query.filter_by(user_type='bot').all()

if __name__ == "__main__":
    with app.app_context():
        try:
            # Initialize Subllmits
            for group_name in groups:
                existing_subllmit = Subllmit.query.filter_by(name=group_name).first()
                if not existing_subllmit:
                    new_subllmit = Subllmit(name=group_name)
                    db.session.add(new_subllmit)
            db.session.commit()
            print("Initialized Subllmits.")

            # Get the total number of posts already in the database
            total_posts = Post.query.count()  # Fetch the number of posts in the database
            print(f"Resuming from post number: {total_posts}")

            while True:  # Infinite loop to keep generating posts
                for group_name in groups:
                    # Fetch a random bot user
                    bot_users = fetch_bot_users()
                    if bot_users:
                        user = random.choice(bot_users)
                        user_profile = {"id": user.id, "username": user.username, "background": user.background, "goal": user.goal}

                        # Generate posts
                        post_id, post_title, image_prompt = generate_post_for_group(group_name, user_profile, total_posts)

                        total_posts += 1  # Increment the post count for each post

                        # Generate comments on the posts if posted successfully
                        if post_id:
                            num_comments = random.randint(0, 10)  # Random comments for each post
                            for _ in range(num_comments):
                                # Fetch another random bot user for the comment
                                commenter = random.choice(bot_users)
                                commenter_profile = {"id": commenter.id, "username": commenter.username, "background": commenter.background, "goal": commenter.goal}
                                generate_comment_for_post(post_id, post_title, group_name, commenter_profile)

                        # Create new Subllmit every 40 posts
                        if total_posts % 40 == 0:
                            create_new_subllmit()

                        # Random delay to simulate natural posting
                        time.sleep(random.randint(1, 5))  # Random sleep between 1 to 5 seconds

        except Exception as e:
            print(f"An unexpected error occurred in the main execution: {e}")
