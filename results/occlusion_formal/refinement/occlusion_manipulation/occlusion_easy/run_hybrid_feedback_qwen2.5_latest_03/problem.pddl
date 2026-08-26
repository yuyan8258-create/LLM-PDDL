(define (problem occlusion-easy)
  (:domain image_occlusion_manipulation)

  (:objects
    T1 - target-brick
    O1 - occluder-brick
    target_slot - target-structural-location
    front_slot - occluder-structural-location
    temp_A - temporary-location
    goal_region - goal-location
  )

  (:init
    (at T1 target_slot)
    (at O1 front_slot)
    (occludes O1 T1)
    (accessible O1)
    (clear O1)
    (clear T1)
    (handempty)
    (free temp_A)
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
