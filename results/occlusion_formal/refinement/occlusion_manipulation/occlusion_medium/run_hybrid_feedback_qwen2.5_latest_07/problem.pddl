(define (problem occlusion-medium)
  (:domain image_occlusion_manipulation)

  (:objects
    T1 - target-brick
    O1 O2 - occluder-brick
    target_slot - target-structural-location
    front_slot - occluder-structural-location
    temp_A temp_B - temporary-location
    goal_region - goal-location
  )

  (:init
    (at T1 target_slot)
    (at O1 front_slot)
    (on O2 O1)
    (occludes O2 O1)
    (occludes O1 T1)
    (clear O2)
    (clear T1)
    (accessible O2)
    (handempty)
    (free temp_A)
    (free temp_B)
    (free goal_region)
  )

  (:goal
    (and
      (at T1 goal_region)
      (handempty)
      (target-relocated)
    )
  )
)
