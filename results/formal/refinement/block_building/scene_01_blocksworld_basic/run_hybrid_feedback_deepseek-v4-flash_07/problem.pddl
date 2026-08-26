(define (problem scene-01-blocksworld-basic)
  (:domain image_block_building)

  (:objects
    blockA blockB blockC
  )

  (:init
    (on blockA blockB)
    (ontable blockB)
    (ontable blockC)
    (clear blockA)
    (clear blockC)
    (handempty)
  )

  (:goal
    (and
      (on blockB blockC)
      (ontable blockA)
      (handempty)
    )
  )
)
