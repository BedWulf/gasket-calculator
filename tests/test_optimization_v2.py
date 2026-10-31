"""Quality mode preserves correctness and a non-increasing result length."""
import unittest

from algorithms.nesting import Part, calculate_sheet, validate_result, NestResult, Placement


class OptimizationV2Tests(unittest.TestCase):
    def test_advanced_not_worse_and_deterministic(self):
        parts = [Part('L','polygon',quantity=2,points=[
                    (0,0),(100,0),(100,20),(30,20),(30,85),(0,85)]),
                 Part('B','rectangle',quantity=2,width=40,height=45),
                 Part('C','circle',quantity=1,diameter=30)]
        baseline=calculate_sheet(parts,180,gap=2,margin=2,length_step=5,quality='standard')
        improved=calculate_sheet(parts,180,gap=2,margin=2,length_step=5,quality='thorough')
        self.assertTrue(validate_result(improved))
        self.assertLessEqual(improved.sheet_length,baseline.sheet_length)
        repeat=calculate_sheet(parts,180,gap=2,margin=2,length_step=5,quality='thorough')
        self.assertEqual(repeat.sheet_length,improved.sheet_length)

    def test_forbidden_rotation_is_rejected(self):
        part=Part('No rotate','rectangle',width=10,height=20,rotate_allowed=False)
        result=NestResult(100,100,[Placement(0,10,10,90)],0,0,1,[part])
        self.assertFalse(validate_result(result))

    def test_invalid_quality_rejected(self):
        with self.assertRaisesRegex(ValueError,'режим'):
            calculate_sheet([Part('x','rectangle',width=10,height=10)],100,quality='ultra')


if __name__ == '__main__':unittest.main()
