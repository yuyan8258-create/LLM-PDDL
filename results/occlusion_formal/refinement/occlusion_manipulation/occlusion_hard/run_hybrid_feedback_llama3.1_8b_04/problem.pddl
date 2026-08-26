(define (problem occlusion-hard)
  (:domain image_occlusion_manipulation)

  (:objects
    T1 - target-brick
    O1 O2 O3 - occluder-brick
    target_slot - target-structural-location
    front_slot - occluder-structural-location
    temp_A temp_B temp_C - temporary-location
    goal_region - goal-location
  )

  (:init
    (at T1 target_slot)
    (at O1 front_slot)
    (on O2 O1)
    (on O3 O2)
    (occludes O3 O2)
    (occludes O2 O1)
    (occludes O1 T1)
    (clear O3)
    (clear T1)
    (accessible O3)
    (handempty)
    (free temp_A)
    (free temp_B)
    (free temp_C)
    (free goal_region)
  )

  (:goal
    (and
      (at T1 goal_region)
      (at O1 front_slot)
      (on O2 O1)
      (on O3 O2)
      (occludes O2 O1)
      (occludes O3 O2)
      (handempty)
      (target-relocated)
    )
  )
)
